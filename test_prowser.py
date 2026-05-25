from prowser.html_parser import HTMLParser, Element, Text
from prowser.css_parser import parse_css, compute_style
from prowser.layout import build_layout_tree

def test_html_parser():
    html = "<html><body><h1>Title</h1><p>Paragraph <a href='/link'>Link</a></p></body></html>"
    parser = HTMLParser(html)
    dom = parser.parse()
    
    assert dom.tag == "html"
    assert len(dom.children) == 1
    
    body = dom.children[0]
    assert body.tag == "body"
    assert len(body.children) == 2
    
    h1 = body.children[0]
    assert h1.tag == "h1"
    assert len(h1.children) == 1
    assert isinstance(h1.children[0], Text)
    assert h1.children[0].text == "Title"
    
    p = body.children[1]
    assert p.tag == "p"
    assert len(p.children) == 2
    assert p.children[0].text == "Paragraph "
    
    a = p.children[1]
    assert a.tag == "a"
    assert a.attributes["href"] == "/link"
    print("HTML parser tests passed")

def test_css_parser():
    css = "body { color: red; background-color: blue; } a { text-decoration: underline; }"
    rules = parse_css(css)
    assert len(rules) == 2
    assert rules[0].selector == "body"
    assert rules[0].declarations["color"] == "red"
    assert rules[0].declarations["background-color"] == "blue"
    assert rules[1].selector == "a"
    assert rules[1].declarations["text-decoration"] == "underline"
    
    html = "<html><body><a style='color: green;'>link</a></body></html>"
    dom = HTMLParser(html).parse()
    compute_style(dom, rules)
    
    body = dom.children[0]
    a = body.children[0]
    
    assert body.style["color"] == "red"
    assert body.style["background-color"] == "blue"
    assert a.style["color"] == "green"
    assert a.style["text-decoration"] == "underline"
    print("CSS parser and styling tests passed")

def test_layout_engine():
    html = "<html><body><div>Block content</div></body></html>"
    dom = HTMLParser(html).parse()
    rules = parse_css("body { margin: 10px; }")
    compute_style(dom, rules)
    
    tree = build_layout_tree(dom)
    
    def dummy_measure(text, size, weight, style):
        return len(text) * 8, 16
        
    tree.layout(0, 0, 800, dummy_measure)
    
    assert tree.width == 800
    body_layout = tree.children[0]
    assert body_layout.x == 10
    assert body_layout.width == 780
    print("Layout engine tests passed")

if __name__ == "__main__":
    test_html_parser()
    test_css_parser()
    test_layout_engine()
