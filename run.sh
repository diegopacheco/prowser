export PYTHONPATH=.
export TK_SILENCE_DEPRECATION=1
if [ ! -x ".venv/bin/python" ]; then
    BASE=""
    for c in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if command -v "$c" >/dev/null 2>&1 && "$c" -c "import tkinter,sys; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)" >/dev/null 2>&1; then
            BASE="$c"
            break
        fi
    done
    if [ -n "$BASE" ]; then
        "$BASE" -m venv .venv
        .venv/bin/python -m pip install --quiet --upgrade pip
        .venv/bin/python -m pip install --quiet -r requirements.txt
    fi
fi
if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python -m prowser.main "$@"
fi
echo "warning: no python with Tk>=8.6 found, the UI may render blank on macOS"
exec python3 -m prowser.main "$@"
