class Node:
    def __init__(self):
        self.parent = None
        self.children = []
        self.style = {}

class Element(Node):
    def __init__(self, tag, attributes):
        super().__init__()
        self.tag = tag.lower()
        self.attributes = {k.lower(): v for k, v in attributes.items()}

class Text(Node):
    def __init__(self, text):
        super().__init__()
        self.text = text

def parse_attributes(attr_str):
    attributes = {}
    i = 0
    while i < len(attr_str):
        while i < len(attr_str) and attr_str[i].isspace():
            i += 1
        if i >= len(attr_str):
            break
        
        name_start = i
        while i < len(attr_str) and not attr_str[i].isspace() and attr_str[i] != "=":
            i += 1
        name = attr_str[name_start:i]
        
        while i < len(attr_str) and attr_str[i].isspace():
            i += 1
            
        if i < len(attr_str) and attr_str[i] == "=":
            i += 1
            while i < len(attr_str) and attr_str[i].isspace():
                i += 1
            if i < len(attr_str) and attr_str[i] in ('"', "'"):
                quote = attr_str[i]
                i += 1
                val_start = i
                while i < len(attr_str) and attr_str[i] != quote:
                    i += 1
                val = attr_str[val_start:i]
                if i < len(attr_str):
                    i += 1
            else:
                val_start = i
                while i < len(attr_str) and not attr_str[i].isspace() and attr_str[i] != ">":
                    i += 1
                val = attr_str[val_start:i]
            attributes[name] = val
        else:
            attributes[name] = ""
            
    return attributes

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []
        self.void_tags = {"meta", "link", "br", "hr", "img", "input"}

    def parse(self):
        i = 0
        root = Element("html", {})
        self.unfinished.append(root)
        
        while i < len(self.body):
            if self.body[i] == "<":
                if self.body.startswith("<!--", i):
                    end = self.body.find("-->", i + 4)
                    if end == -1:
                        break
                    i = end + 3
                elif self.body.startswith("<!", i):
                    end = self.body.find(">", i + 2)
                    if end == -1:
                        break
                    i = end + 1
                else:
                    end = self.body.find(">", i)
                    if end == -1:
                        break
                    tag_content = self.body[i+1:end].strip()
                    i = end + 1
                    
                    if not tag_content:
                        continue
                        
                    if tag_content.startswith("/"):
                        tag_name = tag_content[1:].strip().lower()
                        self.close_tag(tag_name)
                    else:
                        parts = tag_content.split(None, 1)
                        tag_name = parts[0].lower()
                        attr_str = parts[1] if len(parts) > 1 else ""
                        attrs = parse_attributes(attr_str)
                        self.add_tag(tag_name, attrs)
            else:
                end = self.body.find("<", i)
                if end == -1:
                    text_content = self.body[i:]
                    i = len(self.body)
                else:
                    text_content = self.body[i:end]
                    i = end
                
                if text_content:
                    self.add_text(text_content)
                    
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            self.unfinished[-1].children.append(node)
            node.parent = self.unfinished[-1]
            
        return root

    def add_text(self, text):
        if not text.strip():
            return
        node = Text(text)
        if self.unfinished:
            self.unfinished[-1].children.append(node)
            node.parent = self.unfinished[-1]

    def add_tag(self, tag, attrs):
        if tag == "html" and len(self.unfinished) == 1 and self.unfinished[0].tag == "html":
            self.unfinished[0].attributes.update(attrs)
            return
        node = Element(tag, attrs)
        if tag in self.void_tags:
            if self.unfinished:
                self.unfinished[-1].children.append(node)
                node.parent = self.unfinished[-1]
        else:
            self.unfinished.append(node)

    def close_tag(self, tag):
        idx = -1
        for j in range(len(self.unfinished) - 1, 0, -1):
            if self.unfinished[j].tag == tag:
                idx = j
                break
        if idx != -1:
            while len(self.unfinished) > idx + 1:
                node = self.unfinished.pop()
                self.unfinished[-1].children.append(node)
                node.parent = self.unfinished[-1]
            node = self.unfinished.pop()
            if self.unfinished:
                self.unfinished[-1].children.append(node)
                node.parent = self.unfinished[-1]
