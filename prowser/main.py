import sys
from prowser.browser import Browser

def main():
    b = Browser()
    if len(sys.argv) > 1:
        initial_url = sys.argv[1]
        b.root.after(100, lambda: b.open_url(initial_url))
    b.start()

if __name__ == "__main__":
    main()
