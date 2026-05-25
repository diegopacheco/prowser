import re
import sys
import json
import dukpy
from prowser.html_parser import HTMLParser, Element, Text

RUNTIME_JS = """
var window = this;
var LISTENERS = {};
var NODES = {};

function Node(handle) { this.handle = handle; }
Node.prototype.getAttribute = function(attr) { return call_python("getAttribute", this.handle, attr); };
Node.prototype.addEventListener = function(type, fn) {
    LISTENERS[this.handle] = LISTENERS[this.handle] || {};
    LISTENERS[this.handle][type] = LISTENERS[this.handle][type] || [];
    LISTENERS[this.handle][type].push(fn);
};
Object.defineProperty(Node.prototype, "innerHTML", {
    set: function(s) { call_python("innerHTML_set", this.handle, s.toString()); }
});
Object.defineProperty(Node.prototype, "textContent", {
    get: function() { return call_python("getTextContent", this.handle); }
});

function __node(handle) {
    if (!(handle in NODES)) NODES[handle] = new Node(handle);
    return NODES[handle];
}

var console = { log: function() {
    var parts = [];
    for (var i = 0; i < arguments.length; i++) parts.push(String(arguments[i]));
    call_python("log", parts.join(" "));
} };

var document = {
    querySelectorAll: function(sel) {
        return call_python("querySelectorAll", sel).map(function(h) { return __node(h); });
    },
    querySelector: function(sel) {
        var all = call_python("querySelectorAll", sel);
        return all.length ? __node(all[0]) : null;
    },
    getElementById: function(id) {
        var all = call_python("querySelectorAll", "#" + id);
        return all.length ? __node(all[0]) : null;
    }
};

function __dispatch_event(handle, type) {
    var byType = LISTENERS[handle] || {};
    var fns = byType[type] || [];
    var evt = { type: type, _prevented: false, preventDefault: function() { this._prevented = true; } };
    var node = __node(handle);
    for (var i = 0; i < fns.length; i++) {
        try { fns[i].call(node, evt); } catch (e) { console.log("event handler error: " + e); }
    }
    return evt._prevented;
}
"""

def tree_to_list(node, acc):
    acc.append(node)
    for child in node.children:
        tree_to_list(child, acc)
    return acc

def matches_simple(node, simple):
    if not isinstance(node, Element):
        return False
    tag = None
    node_id = None
    classes = []
    for token in re.findall(r"[.#]?[\w-]+|\*", simple):
        if token.startswith("."):
            classes.append(token[1:])
        elif token.startswith("#"):
            node_id = token[1:]
        else:
            tag = token
    if tag and tag != "*" and node.tag != tag.lower():
        return False
    if node_id and node.attributes.get("id") != node_id:
        return False
    if classes:
        node_classes = (node.attributes.get("class") or "").split()
        for c in classes:
            if c not in node_classes:
                return False
    return True

def matches(node, selector):
    parts = selector.split()
    if not parts or not matches_simple(node, parts[-1]):
        return False
    parts = parts[:-1]
    ancestor = node.parent
    i = len(parts) - 1
    while i >= 0 and ancestor:
        if matches_simple(ancestor, parts[i]):
            i -= 1
        ancestor = ancestor.parent
    return i < 0

class JSEngine:
    def __init__(self, browser):
        self.browser = browser
        self.handle_to_node = {}
        self.node_handles = {}
        self.next_handle = 0
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", self.log)
        self.interp.export_function("querySelectorAll", self.query_selector_all)
        self.interp.export_function("getAttribute", self.get_attribute)
        self.interp.export_function("getTextContent", self.get_text_content)
        self.interp.export_function("innerHTML_set", self.inner_html_set)
        self.interp.evaljs(RUNTIME_JS)

    def get_handle(self, node):
        key = id(node)
        if key not in self.node_handles:
            handle = self.next_handle
            self.next_handle += 1
            self.node_handles[key] = handle
            self.handle_to_node[handle] = node
        return self.node_handles[key]

    def log(self, message):
        print(f"[js] {message}", flush=True)

    def query_selector_all(self, selector_text):
        selectors = [s.strip() for s in selector_text.split(",") if s.strip()]
        result = []
        seen = set()
        for node in tree_to_list(self.browser.dom, []):
            if any(matches(node, sel) for sel in selectors):
                handle = self.get_handle(node)
                if handle not in seen:
                    seen.add(handle)
                    result.append(handle)
        return result

    def get_attribute(self, handle, attr):
        node = self.handle_to_node.get(handle)
        if node is None:
            return ""
        return node.attributes.get(attr, "")

    def get_text_content(self, handle):
        node = self.handle_to_node.get(handle)
        if node is None:
            return ""
        parts = []
        for n in tree_to_list(node, []):
            if isinstance(n, Text):
                parts.append(n.text)
        return "".join(parts)

    def inner_html_set(self, handle, html):
        node = self.handle_to_node.get(handle)
        if node is None:
            return
        fragment = HTMLParser(html).parse()
        node.children = []
        for child in fragment.children:
            child.parent = node
            node.children.append(child)
        self.browser.on_dom_changed()

    def run(self, code):
        try:
            self.interp.evaljs(code)
        except Exception as e:
            print(f"[js] script error: {e}", file=sys.stderr, flush=True)

    def dispatch_event(self, node, event_type):
        handle = self.node_handles.get(id(node))
        if handle is None:
            return False
        try:
            return bool(self.interp.evaljs(f"__dispatch_event({handle}, {json.dumps(event_type)})"))
        except Exception as e:
            print(f"[js] dispatch error: {e}", file=sys.stderr, flush=True)
            return False
