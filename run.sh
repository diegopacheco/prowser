export PYTHONPATH=.
export TK_SILENCE_DEPRECATION=1
PY=""
for c in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
    if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c "import tkinter,sys; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)" >/dev/null 2>&1; then
            PY="$c"
            break
        fi
    fi
done
if [ -z "$PY" ]; then
    PY="python3"
    echo "warning: no python with Tk>=8.6 found, the UI may render blank on macOS"
fi
exec "$PY" -m prowser.main "$@"
