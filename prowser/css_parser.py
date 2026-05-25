INHERITED_PROPERTIES = {
    "color",
    "font-size",
    "font-weight",
    "font-style",
    "text-decoration"
}

DEFAULT_STYLESHEET = """
body {
    background-color: #ffffff;
    color: #000000;
    font-size: 16px;
    font-weight: normal;
    font-style: normal;
}
h1 {
    font-size: 28px;
    font-weight: bold;
    margin: 16px;
}
h2 {
    font-size: 22px;
    font-weight: bold;
    margin: 12px;
}
p {
    margin: 10px;
}
a {
    color: #0000ee;
}
"""

class CSSRule:
    def __init__(self, selector, declarations):
        self.selector = selector.strip().lower()
        self.declarations = declarations

def parse_declarations(decl_str):
    declarations = {}
    parts = decl_str.split(";")
    for part in parts:
        if not part.strip():
            continue
        if ":" not in part:
            continue
        prop, val = part.split(":", 1)
        declarations[prop.strip().lower()] = val.strip()
    return declarations

def parse_css(css_str):
    rules = []
    i = 0
    while i < len(css_str):
        if css_str[i].isspace():
            i += 1
            continue
        
        brace_open = css_str.find("{", i)
        if brace_open == -1:
            break
            
        brace_close = css_str.find("}", brace_open)
        if brace_close == -1:
            break
            
        selector_part = css_str[i:brace_open].strip()
        decl_part = css_str[brace_open+1:brace_close].strip()
        
        decls = parse_declarations(decl_part)
        
        selectors = selector_part.split(",")
        for sel in selectors:
            rules.append(CSSRule(sel, decls))
            
        i = brace_close + 1
        
    return rules

def compute_style(node, rules):
    node.style = {}
    
    if node.parent:
        for prop in INHERITED_PROPERTIES:
            if prop in node.parent.style:
                node.style[prop] = node.parent.style[prop]
                
    if hasattr(node, "tag"):
        for rule in rules:
            if rule.selector == node.tag:
                for prop, val in rule.declarations.items():
                    node.style[prop] = val
                    
        if "style" in node.attributes:
            inline_decls = parse_declarations(node.attributes["style"])
            for prop, val in inline_decls.items():
                node.style[prop] = val
                
    for child in node.children:
        compute_style(child, rules)
