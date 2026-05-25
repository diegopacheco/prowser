from prowser.html_parser import Element, Text

BLOCK_TAGS = {
    "html", "body", "div", "h1", "h2", "p", 
    "ul", "li", "section", "nav", "header", "footer"
}

def is_block_node(node):
    if isinstance(node, Text):
        return False
    return node.tag in BLOCK_TAGS

def parse_px(val, default=0):
    if not val:
        return default
    val = val.strip().lower()
    if val.endswith("px"):
        try:
            return int(val[:-2])
        except ValueError:
            return default
    return default

class BlockLayout:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.children = []

    def layout(self, x, y, width, measure_fn):
        self.x = x
        self.y = y
        self.width = width

        margin = parse_px(self.node.style.get("margin", "0px"))
        padding = parse_px(self.node.style.get("padding", "0px"))

        margin_left = parse_px(self.node.style.get("margin-left"), margin)
        margin_right = parse_px(self.node.style.get("margin-right"), margin)
        margin_top = parse_px(self.node.style.get("margin-top"), margin)
        margin_bottom = parse_px(self.node.style.get("margin-bottom"), margin)

        padding_left = parse_px(self.node.style.get("padding-left"), padding)
        padding_right = parse_px(self.node.style.get("padding-right"), padding)
        padding_top = parse_px(self.node.style.get("padding-top"), padding)
        padding_bottom = parse_px(self.node.style.get("padding-bottom"), padding)

        self.x += margin_left
        self.y += margin_top
        self.width -= (margin_left + margin_right)

        content_x = self.x + padding_left
        content_y = self.y + padding_top
        content_width = self.width - (padding_left + padding_right)

        current_y = content_y
        for child in self.children:
            child.layout(content_x, current_y, content_width, measure_fn)
            current_y += child.height

        self.height = (current_y - self.y) + padding_bottom + margin_bottom

    def paint(self, display_list):
        bg_color = self.node.style.get("background-color")
        if bg_color:
            display_list.append({
                "type": "rect",
                "x": self.x,
                "y": self.y,
                "w": self.width,
                "h": self.height,
                "color": bg_color
            })

        for child in self.children:
            child.paint(display_list)

class InlineLayout:
    def __init__(self, node, parent, inline_nodes):
        self.node = node
        self.parent = parent
        self.inline_nodes = inline_nodes
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.display_items = []

    def layout(self, x, y, width, measure_fn):
        self.x = x
        self.y = y
        self.width = width
        self.display_items = []

        cursor_x = 0
        cursor_y = 0
        line_height = 0

        def recurse_inline(dom_node):
            nonlocal cursor_x, cursor_y, line_height
            if isinstance(dom_node, Text):
                words = dom_node.text.split(" ")
                for idx, word in enumerate(words):
                    if not word and idx > 0 and idx < len(words) - 1:
                        continue

                    font_size = parse_px(dom_node.style.get("font-size", "16px"), 16)
                    font_weight = dom_node.style.get("font-weight", "normal")
                    font_style = dom_node.style.get("font-style", "normal")
                    color = dom_node.style.get("color", "#000000")
                    text_decoration = dom_node.style.get("text-decoration", "none")

                    word_width, word_height = measure_fn(word, font_size, font_weight, font_style)
                    space_width, _ = measure_fn(" ", font_size, font_weight, font_style)

                    if cursor_x + word_width > self.width:
                        cursor_x = 0
                        cursor_y += line_height
                        line_height = 0

                    line_height = max(line_height, word_height)

                    self.display_items.append({
                        "x": self.x + cursor_x,
                        "y": self.y + cursor_y,
                        "w": word_width,
                        "h": word_height,
                        "text": word,
                        "font_size": font_size,
                        "font_weight": font_weight,
                        "font_style": font_style,
                        "color": color,
                        "text_decoration": text_decoration,
                        "node": dom_node
                    })

                    cursor_x += word_width + space_width
            else:
                for child in dom_node.children:
                    recurse_inline(child)

        for node in self.inline_nodes:
            recurse_inline(node)

        self.height = cursor_y + line_height

    def paint(self, display_list):
        bg_color = self.node.style.get("background-color")
        if bg_color:
            display_list.append({
                "type": "rect",
                "x": self.x,
                "y": self.y,
                "w": self.width,
                "h": self.height,
                "color": bg_color
            })

        for item in self.display_items:
            display_list.append({
                "type": "text",
                "x": item["x"],
                "y": item["y"],
                "text": item["text"],
                "font_size": item["font_size"],
                "font_weight": item["font_weight"],
                "font_style": item["font_style"],
                "color": item["color"],
                "node": item["node"]
            })
            if item["text_decoration"] == "underline":
                display_list.append({
                    "type": "line",
                    "x1": item["x"],
                    "y1": item["y"] + item["h"] - 2,
                    "x2": item["x"] + item["w"],
                    "y2": item["y"] + item["h"] - 2,
                    "color": item["color"]
                })

def build_layout_tree(node, parent=None):
    if is_block_node(node):
        box = BlockLayout(node, parent)
        has_block_child = any(is_block_node(c) for c in node.children)

        if has_block_child:
            current_inline_group = []
            for child in node.children:
                if is_block_node(child):
                    if current_inline_group:
                        anon_node = Element("anon", {})
                        anon_node.style = node.style.copy()
                        anon_box = InlineLayout(anon_node, box, current_inline_group)
                        box.children.append(anon_box)
                        current_inline_group = []
                    box.children.append(build_layout_tree(child, box))
                else:
                    current_inline_group.append(child)
            if current_inline_group:
                anon_node = Element("anon", {})
                anon_node.style = node.style.copy()
                anon_box = InlineLayout(anon_node, box, current_inline_group)
                box.children.append(anon_box)
        else:
            if node.children:
                inline_box = InlineLayout(node, box, node.children)
                box.children.append(inline_box)
        return box
    else:
        return InlineLayout(node, parent, [node])
