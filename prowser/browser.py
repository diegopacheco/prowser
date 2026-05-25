import base64
import queue
import sys
import threading
import tkinter
import tkinter.font
from html import escape
from urllib.parse import urlencode, unquote_to_bytes
from prowser.network import request, fetch, parse_url
from prowser.html_parser import HTMLParser, Element, Text
from prowser.css_parser import parse_css, compute_style, DEFAULT_STYLESHEET

try:
    from prowser.js_engine import JSEngine
except Exception:
    JSEngine = None

TEXT_INPUT_TYPES = {"text", "search", "email", "url", "tel", "password", "number", ""}
BUTTON_INPUT_TYPES = {"submit", "button", "reset", "image"}

def get_form_node(node):
    curr = node
    while curr:
        if isinstance(curr, Element) and curr.tag == "form":
            return curr
        curr = curr.parent
    return None

def collect_form_params(form, trigger, text_values):
    params = []
    def collect(n):
        if isinstance(n, Element) and n.tag in ("input", "textarea"):
            name = n.attributes.get("name")
            if name:
                itype = "text" if n.tag == "textarea" else n.attributes.get("type", "text").lower()
                if n in text_values:
                    params.append((name, text_values[n]))
                elif itype in BUTTON_INPUT_TYPES:
                    if n is trigger:
                        params.append((name, n.attributes.get("value") or ""))
                else:
                    params.append((name, n.attributes.get("value") or ""))
        for c in n.children:
            collect(c)
    collect(form)
    return params

def get_anchor_node(node):
    curr = node
    while curr:
        if isinstance(curr, Element) and curr.tag == "a":
            return curr
        curr = curr.parent
    return None

class Browser:
    def __init__(self):
        self.root = tkinter.Tk()
        self.root.title("Prowser")
        self.root.geometry("800x600")

        self.nav_frame = tkinter.Frame(self.root, bg="#eeeeee")
        self.nav_frame.pack(fill="x")

        self.back_button = tkinter.Button(self.nav_frame, text="←", command=self.go_back, state="disabled")
        self.back_button.pack(side="left", padx=(8, 0), pady=4)

        self.forward_button = tkinter.Button(self.nav_frame, text="→", command=self.go_forward, state="disabled")
        self.forward_button.pack(side="left", padx=(2, 4), pady=4)

        self.address_label = tkinter.Label(self.nav_frame, text="URL", bg="#eeeeee", fg="#000000")
        self.address_label.pack(side="left", padx=(4, 4), pady=6)

        self.go_button = tkinter.Button(self.nav_frame, text="Go", command=self.go)
        self.go_button.pack(side="right", padx=(4, 8), pady=4)

        self.address_entry = tkinter.Entry(self.nav_frame, width=80, bg="#ffffff", fg="#000000", insertbackground="#000000", relief="sunken", bd=2)
        self.address_entry.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=5)
        self.address_entry.bind("<Return>", lambda e: self.go())

        self.scrollbar = tkinter.Scrollbar(self.root, orient="vertical", command=self.on_scrollbar)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas = tkinter.Canvas(self.root, bg="#ffffff")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.font_cache = {}
        self.dom = None
        self.layout_tree = None
        self.display_list = []
        self.scroll_y = 0
        self.url = ""
        self.load_id = 0
        self.load_queue = queue.Queue()
        self.loading = False
        self.color_cache = {}

        self.focused_input = None
        self.input_text = {}
        self.images = {}
        self.image_pending = set()
        self.image_failed = set()
        self.image_queue = queue.Queue()
        self.image_poll_active = False
        self.history = []
        self.history_index = -1
        self.js = None
        self.rules = []

        self.last_width = 800
        self.last_height = 600

        self.canvas.config(takefocus=1)
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Key>", self.on_key)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.scroll(-40))
        self.canvas.bind("<Button-5>", lambda e: self.scroll(40))

        self.root.bind("<Down>", lambda e: self.scroll_key(40))
        self.root.bind("<Up>", lambda e: self.scroll_key(-40))
        self.root.bind("<space>", lambda e: self.scroll_key(300))

        self.set_address("http://www.google.com")
        self.address_entry.focus_set()
        self.root.after(0, self.load_start_page)

    def on_resize(self, event):
        if event.width != self.last_width or event.height != self.last_height:
            self.last_width = event.width
            self.last_height = event.height
            if self.dom:
                self.layout_and_paint()

    def on_mouse_wheel(self, event):
        if event.delta:
            if abs(event.delta) < 10:
                self.scroll(-event.delta * 20)
            else:
                self.scroll(-int(event.delta / 120) * 40)

    def scroll_key(self, amount):
        if self.focused_input is not None:
            return
        if isinstance(self.root.focus_get(), tkinter.Entry):
            return
        self.scroll(amount)

    def scroll(self, amount):
        doc_height = self.layout_tree.height if self.layout_tree else 0
        view_height = self.canvas.winfo_height()
        max_scroll = max(0, doc_height - view_height)
        self.scroll_y = max(0, min(self.scroll_y + amount, max_scroll))
        self.render()

    def on_scrollbar(self, *args):
        if not self.layout_tree:
            return
        doc_height = self.layout_tree.height
        view_height = self.canvas.winfo_height()
        max_scroll = max(0, doc_height - view_height)
        if args[0] == "moveto":
            self.scroll_y = int(max(0, min(float(args[1]) * doc_height, max_scroll)))
        elif args[0] == "scroll":
            step = view_height if args[2] == "pages" else 40
            self.scroll_y = max(0, min(self.scroll_y + int(args[1]) * step, max_scroll))
        self.render()

    def update_scrollbar(self):
        doc_height = self.layout_tree.height if self.layout_tree else 0
        view_height = self.canvas.winfo_height()
        if doc_height <= view_height or doc_height <= 0:
            self.scrollbar.set(0, 1)
            return
        first = self.scroll_y / doc_height
        last = min(1.0, (self.scroll_y + view_height) / doc_height)
        self.scrollbar.set(first, last)

    def go(self):
        url = self.normalize_url(self.address_entry.get())
        if not url:
            return
        self.set_address(url)
        self.load(url)

    @staticmethod
    def normalize_url(url):
        url = url.strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            return "http://" + url
        return url

    def set_address(self, url):
        self.address_entry.delete(0, tkinter.END)
        self.address_entry.insert(0, url)

    def open_url(self, url):
        url = self.normalize_url(url)
        if not url:
            return
        self.set_address(url)
        self.load(url)

    def load(self, url, push=True):
        if push:
            del self.history[self.history_index + 1:]
            self.history.append(url)
            self.history_index = len(self.history) - 1
        self.update_nav_buttons()
        self.images.clear()
        self.image_pending.clear()
        self.image_failed.clear()
        self.focused_input = None
        self.input_text.clear()
        self.url = url
        self.load_id += 1
        load_id = self.load_id
        self.loading = True
        self.go_button.config(state="disabled")
        self.show_message(f"Loading {url}")
        threading.Thread(target=self.fetch_url, args=(load_id, url), daemon=True).start()
        self.root.after(50, self.check_load_result)

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            url = self.history[self.history_index]
            self.set_address(url)
            self.load(url, push=False)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            url = self.history[self.history_index]
            self.set_address(url)
            self.load(url, push=False)

    def update_nav_buttons(self):
        self.back_button.config(state="normal" if self.history_index > 0 else "disabled")
        self.forward_button.config(state="normal" if self.history_index < len(self.history) - 1 else "disabled")

    def fetch_url(self, load_id, url):
        try:
            status, headers, body = request(url)
        except Exception as e:
            self.load_queue.put((load_id, url, None, e))
            return
        self.load_queue.put((load_id, url, body, None))

    def check_load_result(self):
        while True:
            try:
                load_id, url, body, error = self.load_queue.get_nowait()
            except queue.Empty:
                if self.loading:
                    self.root.after(50, self.check_load_result)
                return
            if load_id == self.load_id:
                break
        self.loading = False
        self.go_button.config(state="normal")
        if error:
            self.show_error(f"Error loading {url}: {error}")
            return
        try:
            self.render_html(body, run_scripts=True)
        except Exception as e:
            self.show_error(f"Error rendering {url}: {e}")

    def render_html(self, body, run_scripts=False):
        parser = HTMLParser(body)
        self.dom = parser.parse()
        self.js = None

        rules = parse_css(DEFAULT_STYLESHEET)

        style_content = []
        def find_style_tags(node):
            if isinstance(node, Element) and node.tag == "style":
                for child in node.children:
                    if isinstance(child, Text):
                        style_content.append(child.text)
            for child in node.children:
                find_style_tags(child)

        find_style_tags(self.dom)
        for css in style_content:
            rules.extend(parse_css(css))

        self.rules = rules
        compute_style(self.dom, rules)
        if run_scripts and JSEngine is not None:
            self.run_scripts()
        self.layout_and_paint()

    def run_scripts(self):
        scripts = []
        def find_scripts(node):
            if isinstance(node, Element) and node.tag == "script" and "src" not in node.attributes:
                text = "".join(c.text for c in node.children if isinstance(c, Text))
                if text.strip():
                    scripts.append(text)
            for child in node.children:
                find_scripts(child)
        find_scripts(self.dom)
        if not scripts:
            return
        try:
            self.js = JSEngine(self)
        except Exception as e:
            print(f"[js] init error: {e}", file=sys.stderr, flush=True)
            self.js = None
            return
        for code in scripts:
            self.js.run(code)

    def on_dom_changed(self):
        compute_style(self.dom, self.rules)
        self.layout_and_paint(reset_scroll=False)

    def show_message(self, message):
        message_html = f"<html><body><p>{message}</p></body></html>"
        self.render_html(message_html)

    def layout_and_paint(self, reset_scroll=True):
        from prowser.layout import build_layout_tree
        self.layout_tree = build_layout_tree(self.dom)

        width = self.canvas.winfo_width()
        if width <= 1:
            width = 800

        def measure(text, size, weight, style):
            w_val, h_val = self.get_font_metrics(size, weight, style, text)
            return w_val, h_val

        self.layout_tree.layout(0, 0, width, measure)

        self.display_list = []
        self.layout_tree.paint(self.display_list)
        if reset_scroll:
            self.scroll_y = 0
        else:
            doc_height = self.layout_tree.height
            view_height = self.canvas.winfo_height()
            self.scroll_y = max(0, min(self.scroll_y, max(0, doc_height - view_height)))
        self.render()

    def get_font_metrics(self, size, weight, style, text):
        weight_map = "bold" if weight == "bold" else "normal"
        slant_map = "italic" if style == "italic" else "roman"
        key = (size, weight_map, slant_map)
        if key not in self.font_cache:
            self.font_cache[key] = tkinter.font.Font(family="Arial", size=size, weight=weight_map, slant=slant_map)
        f = self.font_cache[key]
        return f.measure(text), f.metrics("linespace")

    def normalize_color(self, color, fallback):
        key = (color, fallback)
        if key in self.color_cache:
            return self.color_cache[key]
        if color is None:
            self.color_cache[key] = fallback
            return fallback
        val = str(color).strip()
        if not val:
            self.color_cache[key] = fallback
            return fallback
        try:
            self.root.winfo_rgb(val)
            self.color_cache[key] = val
            return val
        except Exception:
            self.color_cache[key] = fallback
            return fallback

    def render(self):
        self.canvas.delete("all")
        for item in self.display_list:
            if item["type"] == "image":
                node = item["node"]
                photo = self.images.get(node)
                if photo is not None:
                    try:
                        self.canvas.create_image(item["x"], item["y"] - self.scroll_y, anchor="nw", image=photo)
                    except Exception:
                        self.draw_image_placeholder(item)
                else:
                    if node not in self.image_failed and node not in self.image_pending:
                        self.start_image_load(node)
                    self.draw_image_placeholder(item)
            elif item["type"] == "control":
                self.draw_control(item)
            elif item["type"] == "rect":
                try:
                    fill_color = self.normalize_color(item["color"], "")
                    outline_color = self.normalize_color(item.get("outline", ""), "")
                    self.canvas.create_rectangle(
                        item["x"], item["y"] - self.scroll_y,
                        item["x"] + item["w"], item["y"] + item["h"] - self.scroll_y,
                        fill=fill_color, outline=outline_color
                    )
                except Exception:
                    pass
            elif item["type"] == "text":
                weight_map = "bold" if item["font_weight"] == "bold" else "normal"
                slant_map = "italic" if item["font_style"] == "italic" else "roman"
                key = (item["font_size"], weight_map, slant_map)
                f = self.font_cache[key]
                try:
                    text_color = self.normalize_color(item["color"], "#000000")
                    self.canvas.create_text(
                        item["x"], item["y"] - self.scroll_y,
                        text=item["text"], font=f, fill=text_color, anchor="nw"
                    )
                except Exception:
                    pass
            elif item["type"] == "line":
                try:
                    line_color = self.normalize_color(item["color"], "#000000")
                    self.canvas.create_line(
                        item["x1"], item["y1"] - self.scroll_y,
                        item["x2"], item["y2"] - self.scroll_y,
                        fill=line_color
                    )
                except Exception:
                    pass
        self.update_scrollbar()

    def font_key(self, font_size, font_weight, font_style):
        weight_map = "bold" if font_weight == "bold" else "normal"
        slant_map = "italic" if font_style == "italic" else "roman"
        return (font_size, weight_map, slant_map)

    def get_font(self, font_size, font_weight, font_style):
        key = self.font_key(font_size, font_weight, font_style)
        if key not in self.font_cache:
            self.get_font_metrics(font_size, font_weight, font_style, "")
        return self.font_cache[key]

    def input_value(self, item):
        node = item["node"]
        if node in self.input_text:
            return self.input_text[node]
        return node.attributes.get("value") or ""

    def draw_control(self, item):
        font = self.get_font(item["font_size"], item["font_weight"], item["font_style"])
        top = item["y"] - self.scroll_y
        if item["input_type"] in TEXT_INPUT_TYPES:
            focused = self.focused_input is item["node"]
            outline = "#1a73e8" if focused else "#9a9a9a"
            try:
                self.canvas.create_rectangle(
                    item["x"], top, item["x"] + item["w"], top + item["h"],
                    fill="#ffffff", outline=outline
                )
            except Exception:
                pass
            text = self.input_value(item)
            text_fill = "#000000"
            is_placeholder = False
            if not text and not focused and item.get("label"):
                text = item["label"]
                text_fill = "#888888"
                is_placeholder = True
            max_text_w = item["w"] - 12
            while text and font.measure(text) > max_text_w:
                text = text[:-1] if is_placeholder else text[1:]
            text_x = item["x"] + 6
            text_y = item["y"] + (item["h"] - font.metrics("linespace")) // 2 - self.scroll_y
            try:
                self.canvas.create_text(text_x, text_y, text=text, font=font, fill=text_fill, anchor="nw")
            except Exception:
                pass
            if focused:
                cursor_x = text_x + font.measure(text)
                self.canvas.create_line(cursor_x, text_y, cursor_x, text_y + font.metrics("linespace"), fill="#000000")
            return
        try:
            self.canvas.create_rectangle(
                item["x"], top, item["x"] + item["w"], top + item["h"],
                fill="#f0f0f0", outline="#9a9a9a"
            )
        except Exception:
            pass
        text_color = self.normalize_color(item["color"], "#000000")
        try:
            self.canvas.create_text(
                item["x"] + 8, item["y"] + 5 - self.scroll_y,
                text=item["label"], font=font, fill=text_color, anchor="nw"
            )
        except Exception:
            pass

    def draw_image_placeholder(self, item):
        try:
            self.canvas.create_rectangle(
                item["x"], item["y"] - self.scroll_y,
                item["x"] + item["w"], item["y"] + item["h"] - self.scroll_y,
                outline="#cccccc", fill="#f4f4f4"
            )
        except Exception:
            pass
        alt = item.get("alt") or ""
        if alt:
            font = self.get_font(item["font_size"], item["font_weight"], item["font_style"])
            try:
                self.canvas.create_text(
                    item["x"] + 4, item["y"] + 4 - self.scroll_y,
                    text=alt, font=font, fill="#666666", anchor="nw"
                )
            except Exception:
                pass

    def resolve_image_url(self, src):
        if src.startswith("//"):
            scheme, host, port, path = parse_url(self.url)
            return f"{scheme}:{src}"
        return self.resolve_url(src)

    def decode_data_uri(self, src):
        header, _, data = src[5:].partition(",")
        if "base64" in header:
            return base64.b64decode(data)
        return unquote_to_bytes(data)

    def start_image_load(self, node):
        src = node.attributes.get("src", "")
        if not src:
            self.image_failed.add(node)
            return
        self.image_pending.add(node)
        threading.Thread(target=self.fetch_image, args=(node, src), daemon=True).start()
        if not self.image_poll_active:
            self.image_poll_active = True
            self.root.after(50, self.check_image_queue)

    def fetch_image(self, node, src):
        try:
            if src.startswith("data:"):
                raw = self.decode_data_uri(src)
            else:
                status, headers, raw = fetch(self.resolve_image_url(src))
            self.image_queue.put((node, raw, None))
        except Exception as e:
            self.image_queue.put((node, None, e))

    def check_image_queue(self):
        self.image_poll_active = False
        changed = False
        while True:
            try:
                node, raw, error = self.image_queue.get_nowait()
            except queue.Empty:
                break
            self.image_pending.discard(node)
            if error or not raw:
                self.image_failed.add(node)
                continue
            try:
                photo = tkinter.PhotoImage(data=base64.b64encode(raw).decode("ascii"))
            except Exception:
                self.image_failed.add(node)
                continue
            max_w = max(1, self.canvas.winfo_width() - 20)
            if photo.width() > max_w:
                photo = photo.subsample(photo.width() // max_w + 1)
            node.render_w = photo.width()
            node.render_h = photo.height()
            self.images[node] = photo
            changed = True
        if self.image_pending and not self.image_poll_active:
            self.image_poll_active = True
            self.root.after(50, self.check_image_queue)
        if changed and self.dom:
            self.layout_and_paint(reset_scroll=False)

    def on_click(self, event):
        click_x = event.x
        click_y = event.y + self.scroll_y
        self.focused_input = None

        for item in self.display_list:
            if item["type"] == "control":
                if not (item["x"] <= click_x <= item["x"] + item["w"] and item["y"] <= click_y <= item["y"] + item["h"]):
                    continue
                if item["input_type"] in BUTTON_INPUT_TYPES:
                    self.submit_form(item["node"])
                    return
                if item["input_type"] in TEXT_INPUT_TYPES:
                    self.focused_input = item["node"]
                    self.canvas.focus_set()
                    self.render()
                    return

        clicked_node = None
        for item in self.display_list:
            if item["type"] == "text":
                size = item["font_size"]
                weight = item["font_weight"]
                style = item["font_style"]
                text = item["text"]
                w_val, h_val = self.get_font_metrics(size, weight, style, text)
                if item["x"] <= click_x <= item["x"] + w_val and item["y"] <= click_y <= item["y"] + h_val:
                    clicked_node = item["node"]
                    break
            elif item["type"] == "image":
                if item["x"] <= click_x <= item["x"] + item["w"] and item["y"] <= click_y <= item["y"] + item["h"]:
                    clicked_node = item["node"]
                    break

        if clicked_node and self.js:
            prevented = False
            node = clicked_node
            while node:
                if self.js.dispatch_event(node, "click"):
                    prevented = True
                node = node.parent
            if prevented:
                self.render()
                return

        if clicked_node:
            anchor = get_anchor_node(clicked_node)
            if anchor and "href" in anchor.attributes:
                href = anchor.attributes["href"]
                new_url = self.resolve_url(href)
                self.address_entry.delete(0, tkinter.END)
                self.address_entry.insert(0, new_url)
                self.load(new_url)
                return
        self.render()

    def on_key(self, event):
        if self.focused_input is None:
            return
        node = self.focused_input
        current = self.input_text.get(node, node.attributes.get("value") or "")
        keysym = event.keysym
        if keysym == "Return":
            self.submit_form(node)
            return "break"
        if keysym == "BackSpace":
            self.input_text[node] = current[:-1]
        elif keysym in ("Escape", "Tab"):
            self.focused_input = None
        elif len(event.char) == 1 and event.char.isprintable():
            self.input_text[node] = current + event.char
        else:
            return "break"
        self.render()
        return "break"

    def resolve_url(self, href):
        if href.startswith("http://") or href.startswith("https://"):
            return href

        scheme, host, port, path = parse_url(self.url)

        if href.startswith("/"):
            return f"{scheme}://{host}:{port}{href}"
        else:
            parent_path = path.rsplit("/", 1)[0]
            if not parent_path.startswith("/"):
                parent_path = "/" + parent_path
            if parent_path.endswith("/"):
                return f"{scheme}://{host}:{port}{parent_path}{href}"
            else:
                return f"{scheme}://{host}:{port}{parent_path}/{href}"

    def submit_form(self, node):
        form = get_form_node(node)
        if not form:
            return
        params = collect_form_params(form, node, dict(self.input_text))
        action = form.attributes.get("action") or ""
        url = self.resolve_url(action) if action else self.url
        query = urlencode(params)
        if query:
            url = url + ("&" if "?" in url else "?") + query
        self.set_address(url)
        self.load(url)

    def show_error(self, message):
        print(f"[prowser] {message}", file=sys.stderr, flush=True)
        error_html = f"<html><body><h1>Error</h1><p>{escape(message)}</p></body></html>"
        parser = HTMLParser(error_html)
        self.dom = parser.parse()
        rules = parse_css(DEFAULT_STYLESHEET)
        compute_style(self.dom, rules)
        self.layout_and_paint()

    def start(self):
        self.root.mainloop()

    def load_start_page(self):
        start_html = "<html><body><h1>Welcome to Prowser</h1><p>Type a website address in the entry field at the top and click Go or press Enter to navigate.</p></body></html>"
        self.url = "start://"
        parser = HTMLParser(start_html)
        self.dom = parser.parse()
        rules = parse_css(DEFAULT_STYLESHEET)
        compute_style(self.dom, rules)
        self.layout_and_paint()
