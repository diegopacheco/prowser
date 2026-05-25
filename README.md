# prowser

![prowser rendering google.com](docs/prowser-google.png)

The screenshot above shows prowser loading `http://www.google.com`. From top to bottom it shows the navigation bar with working Back (←) and Forward (→) buttons, the address field and the Go button; the page links (About, Store, Gmail, Images, Sign in); the Google logo rendered from a real PNG image fetched over the network; and the search box, which is a clickable, editable field. Type a query and press Enter to submit the search form. A vertical scroll bar appears on the right for pages taller than the window. prowser runs page JavaScript through an embedded engine with a minimal DOM, so simple scripts (querying elements, reading attributes, setting `innerHTML`, click handlers) work; it is not a full browser, so image rendering is limited to the PNG and GIF formats Tk supports, and pages built around large JavaScript frameworks (such as Google's search results) fall back to their no-script content.

prowser is a simple web browser written in Python using only the standard library.

## Features
- Raw socket HTTP/HTTPS client with automatic status redirect handling.
- Tag and text tokenization HTML parser producing a DOM tree, with raw text handling for `script` and `style` so page content is never lost.
- Style sheet selector rule processor and inline CSS resolver.
- Block and inline coordinate layout engine with text wrapping.
- Tkinter GUI canvas interface with address navigation, Back and Forward history buttons, a vertical scroll bar, mouse and keyboard scrolling, and click navigation support.
- Image rendering for PNG and GIF (including `data:` URIs) fetched over the network.
- Clickable, editable text input and textarea fields with HTML form submission over GET.
- Embedded JavaScript engine (Duktape via `dukpy`) that runs inline scripts against a minimal DOM (`querySelectorAll`, `getElementById`, `getAttribute`, `innerHTML`, `addEventListener` click handlers, `console.log`).
- Errors are reported both on the page and on the console.

## Getting Started

### Prerequisites
- Python 3.x
- Tkinter built against Tk 8.6 or newer (the Tk 8.5 that ships with the macOS system Python does not render correctly). `run.sh` automatically selects a Python whose Tk is 8.6 or newer.
- The JavaScript engine uses the `dukpy` package. On first run, `run.sh` creates a local `.venv` and installs the dependency from `requirements.txt`. JavaScript is optional: if `dukpy` is unavailable the browser still runs without script execution.

### Execution
Run the browser using the execution script:
```bash
./run.sh [URL]
```
If no URL is provided, type the address in the navigation bar and click the Go button.

### Testing
Execute the verification test suite:
```bash
python3 test_prowser.py
```

### Packaging
Create a distribution package tarball:
```bash
./release.sh
```
This creates a `prowser.tar.gz` bundle containing the sources, design document, scripts, and documentation.
