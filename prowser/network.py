import socket
import ssl

def decode_chunked(data):
    result = bytearray()
    i = 0
    while i < len(data):
        line_end = data.find(b"\r\n", i)
        if line_end == -1:
            break
        size_text = data[i:line_end].split(b";", 1)[0].strip()
        try:
            size = int(size_text, 16)
        except ValueError:
            return data
        i = line_end + 2
        if size == 0:
            break
        result.extend(data[i:i + size])
        i += size + 2
    return bytes(result)

def get_charset(headers):
    content_type = headers.get("content-type", "")
    parts = content_type.split(";")
    for part in parts[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value.strip("\"'")
    return "utf-8"

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

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def fetch(url, redirect_limit=5):
    if redirect_limit <= 0:
        raise Exception("Too many redirects")

    scheme, host, port, path = parse_url(url)
    s = socket.create_connection((host, port), timeout=15)

    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)
        s.settimeout(15)

    req_headers = f"GET {path} HTTP/1.1\r\n"
    req_headers += f"Host: {host}\r\n"
    req_headers += "Connection: close\r\n"
    req_headers += f"User-Agent: {USER_AGENT}\r\n"
    req_headers += "Accept: text/html,image/png,image/gif,image/*,*/*\r\n"
    req_headers += "Accept-Encoding: identity\r\n"
    req_headers += "\r\n"

    s.send(req_headers.encode("utf-8"))

    response = bytearray()
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        response.extend(chunk)
    s.close()

    header_bytes, _, body_bytes = bytes(response).partition(b"\r\n\r\n")
    header_part = header_bytes.decode("iso-8859-1", errors="replace")

    header_lines = header_part.split("\r\n")
    status_line = header_lines[0]
    _, status_code_str, _ = status_line.split(" ", 2)
    status_code = int(status_code_str)

    headers = {}
    for line in header_lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    if headers.get("transfer-encoding", "").lower() == "chunked":
        body_bytes = decode_chunked(body_bytes)

    if status_code in (301, 302, 303, 307, 308) and "location" in headers:
        loc = headers["location"]
        if not (loc.startswith("http://") or loc.startswith("https://")):
            if loc.startswith("/"):
                loc = f"{scheme}://{host}:{port}{loc}"
            else:
                parent_path = path.rsplit("/", 1)[0]
                loc = f"{scheme}://{host}:{port}{parent_path}/{loc}"
        return fetch(loc, redirect_limit - 1)

    return status_code, headers, body_bytes

def request(url, redirect_limit=5):
    status_code, headers, body_bytes = fetch(url, redirect_limit)
    body = body_bytes.decode(get_charset(headers), errors="replace")
    return status_code, headers, body
