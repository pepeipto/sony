#!/bin/zsh
# Comprobación de salud de Sony (ver comprobar.py). Uso: ~/IA/sony/comprobar.sh [--api]
PY="$HOME/IA/sony/venv/bin/python"; [ -x "$PY" ] || PY="/opt/homebrew/bin/python3"
exec "$PY" -I "$HOME/IA/sony/comprobar.py" "$@"
