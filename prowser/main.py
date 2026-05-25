import sys
from prowser.browser import Browser

def main():
    b = Browser()
    if len(sys.argv) > 1:
        initial_url = sys.argv[1]
        b.address_entry.delete(0, "end")
        b.address_entry.insert(0, initial_url)
        b.load(initial_url)
    b.start()

if __name__ == "__main__":
    main()
