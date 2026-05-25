from prowser.html_parser import HTMLParser, Element, Text
from prowser.css_parser import parse_css, compute_style
from prowser.layout import build_layout_tree
from prowser.browser import Browser
from prowser.network import decode_chunked, get_charset

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

def test_hidden_nodes_do_not_render():
    html = "<html><head><title>Hidden</title><script>secret()</script></head><body><p>Visible</p></body></html>"
    dom = HTMLParser(html).parse()
    compute_style(dom, parse_css(""))
    tree = build_layout_tree(dom)
    tree.layout(0, 0, 800, lambda text, size, weight, style: (len(text) * 8, 16))
    display = []
    tree.paint(display)
    text = " ".join(item["text"] for item in display if item["type"] == "text")
    assert "Visible" in text
    assert "Hidden" not in text
    assert "secret" not in text
    print("Hidden node tests passed")

def test_input_rendering():
    html = "<html><body><form><input name='q'><input type='submit' value='Search'></form></body></html>"
    dom = HTMLParser(html).parse()
    compute_style(dom, parse_css(""))
    tree = build_layout_tree(dom)
    tree.layout(0, 0, 800, lambda text, size, weight, style: (len(text) * 8, 16))
    display = []
    tree.paint(display)
    rects = [item for item in display if item["type"] == "rect" and item.get("outline")]
    text = " ".join(item["text"] for item in display if item["type"] == "text")
    assert len(rects) == 2
    assert "Search" in text
    print("Input rendering tests passed")

def test_chunked_decode():
    body = decode_chunked(b"5\r\nHello\r\n6\r\n world\r\n0\r\n\r\n")
    assert body == b"Hello world"
    assert get_charset({"content-type": "text/html; charset=ISO-8859-1"}) == "ISO-8859-1"
    assert get_charset({}) == "utf-8"
    print("Chunked response tests passed")

def test_url_normalization():
    assert Browser.normalize_url("www.google.com") == "http://www.google.com"
    assert Browser.normalize_url(" http://localhost:8000 ") == "http://localhost:8000"
    assert Browser.normalize_url("https://google.com") == "https://google.com"
    assert Browser.normalize_url(" ") == ""
    print("URL normalization tests passed")

if __name__ == "__main__":
    test_html_parser()
    test_css_parser()
    test_layout_engine()
    test_hidden_nodes_do_not_render()
    test_input_rendering()
    test_chunked_decode()
    test_url_normalization()
