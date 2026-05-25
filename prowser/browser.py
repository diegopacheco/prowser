import tkinter
import tkinter.font
from prowser.network import request, parse_url
from prowser.html_parser import HTMLParser, Element, Text
from prowser.css_parser import parse_css, compute_style, DEFAULT_STYLESHEET

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

        self.nav_frame = tkinter.Frame(self.root, bg="#f3f3f3")
        self.nav_frame.pack(fill="x")
        self.nav_frame.columnconfigure(1, weight=1)

        self.address_label = tkinter.Label(self.nav_frame, text="URL", bg="#f3f3f3", fg="#000000")
        self.address_label.grid(row=0, column=0, padx=(8, 4), pady=7, sticky="w")

        self.address_box = tkinter.Frame(self.nav_frame, bg="#ffffff", highlightbackground="#9a9a9a", highlightthickness=1, bd=1, relief="solid")
        self.address_box.grid(row=0, column=1, padx=(0, 6), pady=6, sticky="ew")

        self.address_entry = tkinter.Entry(self.address_box, width=60, bg="#ffffff", fg="#000000", insertbackground="#000000", relief="flat", bd=0)
        self.address_entry.pack(fill="x", expand=True, padx=6, pady=3)
        self.address_entry.bind("<Return>", lambda e: self.go())

        self.go_button = tkinter.Button(self.nav_frame, text="Go", command=self.go, highlightbackground="#f3f3f3")
        self.go_button.grid(row=0, column=2, padx=(0, 8), pady=5, sticky="e")

        self.canvas = tkinter.Canvas(self.root, bg="#ffffff")
        self.canvas.pack(fill="both", expand=True)

        self.font_cache = {}
        self.dom = None
        self.layout_tree = None
        self.display_list = []
        self.scroll_y = 0
        self.url = ""

        self.last_width = 800
        self.last_height = 600

        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.scroll(-40))
        self.canvas.bind("<Button-5>", lambda e: self.scroll(40))

        self.root.bind("<Down>", lambda e: self.scroll(40))
        self.root.bind("<Up>", lambda e: self.scroll(-40))
        self.root.bind("<space>", lambda e: self.scroll(300))

        self.address_entry.focus_set()
        self.load_start_page()

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

    def scroll(self, amount):
        doc_height = self.layout_tree.height if self.layout_tree else 0
        view_height = self.canvas.winfo_height()
        max_scroll = max(0, doc_height - view_height)
        self.scroll_y = max(0, min(self.scroll_y + amount, max_scroll))
        self.render()

    def go(self):
        url = self.address_entry.get().strip()
        if not url:
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url
            self.address_entry.delete(0, tkinter.END)
            self.address_entry.insert(0, url)
        self.load(url)

    def load(self, url):
        self.url = url
        try:
            status, headers, body = request(url)
        except Exception as e:
            self.show_error(f"Error loading {url}: {e}")
            return

        parser = HTMLParser(body)
        self.dom = parser.parse()

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

        compute_style(self.dom, rules)
        self.layout_and_paint()

    def layout_and_paint(self):
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
        self.scroll_y = 0
        self.render()

    def get_font_metrics(self, size, weight, style, text):
        weight_map = "bold" if weight == "bold" else "normal"
        slant_map = "italic" if style == "italic" else "roman"
        key = (size, weight_map, slant_map)
        if key not in self.font_cache:
            self.font_cache[key] = tkinter.font.Font(family="Arial", size=size, weight=weight_map, slant=slant_map)
        f = self.font_cache[key]
        return f.measure(text), f.metrics("linespace")

    def render(self):
        self.canvas.delete("all")
        for item in self.display_list:
            if item["type"] == "rect":
                try:
                    self.canvas.create_rectangle(
                        item["x"], item["y"] - self.scroll_y,
                        item["x"] + item["w"], item["y"] + item["h"] - self.scroll_y,
                        fill=item["color"], outline=""
                    )
                except Exception:
                    pass
            elif item["type"] == "text":
                weight_map = "bold" if item["font_weight"] == "bold" else "normal"
                slant_map = "italic" if item["font_style"] == "italic" else "roman"
                key = (item["font_size"], weight_map, slant_map)
                f = self.font_cache[key]
                try:
                    self.canvas.create_text(
                        item["x"], item["y"] - self.scroll_y,
                        text=item["text"], font=f, fill=item["color"], anchor="nw"
                    )
                except Exception:
                    pass
            elif item["type"] == "line":
                try:
                    self.canvas.create_line(
                        item["x1"], item["y1"] - self.scroll_y,
                        item["x2"], item["y2"] - self.scroll_y,
                        fill=item["color"]
                    )
                except Exception:
                    pass

    def on_click(self, event):
        click_x = event.x
        click_y = event.y + self.scroll_y

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

        if clicked_node:
            anchor = get_anchor_node(clicked_node)
            if anchor and "href" in anchor.attributes:
                href = anchor.attributes["href"]
                new_url = self.resolve_url(href)
                self.address_entry.delete(0, tkinter.END)
                self.address_entry.insert(0, new_url)
                self.load(new_url)

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

    def show_error(self, message):
        error_html = f"<html><body><h1>Error</h1><p>{message}</p></body></html>"
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
