import socket
import ssl

def parse_url(url):
    if url.startswith("http://"):
        scheme = "http"
        url = url[7:]
    elif url.startswith("https://"):
        scheme = "https"
        url = url[8:]
    else:
        scheme = "http"

    if "/" in url:
        host, path = url.split("/", 1)
        path = "/" + path
    else:
        host = url
        path = "/"

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)
    else:
        port = 80 if scheme == "http" else 443

    return scheme, host, port, path

def request(url, redirect_limit=5):
    if redirect_limit <= 0:
        raise Exception("Too many redirects")

    scheme, host, port, path = parse_url(url)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)

    s.connect((host, port))
    
    req_headers = f"GET {path} HTTP/1.1\r\n"
    req_headers += f"Host: {host}\r\n"
    req_headers += "Connection: close\r\n"
    req_headers += "User-Agent: prowser\r\n"
    req_headers += "\r\n"
    
    s.send(req_headers.encode("utf-8"))
    
    response = bytearray()
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        response.extend(chunk)
    s.close()
    
    response_str = response.decode("utf-8", errors="replace")
    header_part, _, body = response_str.partition("\r\n\r\n")
    
    header_lines = header_part.split("\r\n")
    status_line = header_lines[0]
    _, status_code_str, _ = status_line.split(" ", 2)
    status_code = int(status_code_str)
    
    headers = {}
    for line in header_lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
            
    if status_code in (301, 302, 303, 307, 308):
        if "location" in headers:
            loc = headers["location"]
            if not (loc.startswith("http://") or loc.startswith("https://")):
                if loc.startswith("/"):
                    loc = f"{scheme}://{host}:{port}{loc}"
                else:
                    parent_path = path.rsplit("/", 1)[0]
                    loc = f"{scheme}://{host}:{port}{parent_path}/{loc}"
            return request(loc, redirect_limit - 1)
            
    return status_code, headers, body
