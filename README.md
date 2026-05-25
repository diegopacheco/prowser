# prowser

prowser is a simple web browser written in Python using only the standard library.

## Features
- Raw socket HTTP/HTTPS client with automatic status redirect handling.
- Tag and text tokenization HTML parser producing a DOM tree.
- Style sheet selector rule processor and inline CSS resolver.
- Block and inline coordinate layout engine with text wrapping.
- Tkinter GUI canvas interface with address navigation, page scrolling, and click navigation support.

## Getting Started

### Prerequisites
- Python 3.x
- Tkinter library

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
