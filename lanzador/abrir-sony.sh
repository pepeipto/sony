#!/bin/bash
# Lo ejecuta la app «IA Sony» en cada doble clic. Arranca el panel si hace falta y abre la ventana de Sony.
# Sale con 3 si la ventana ya está abierta (la app la trae al frente), 0 si la ha abierto, 1 si el panel no arranca.
IA="$HOME/IA"; PANEL="$IA/sony/panel"; PERFIL="$IA/sony/chrome-app"; URL="http://127.0.0.1:8099/chat"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; LOG="$IA/logs/lanzador.log"
mkdir -p "$IA/logs" "$PERFIL"
echo "$(date '+%F %T') doble clic" >> "$LOG"
if ! curl -s -m2 -o /dev/null "http://127.0.0.1:8099/api/chat/estado"; then
  for p in $(lsof -ti tcp:8099 -sTCP:LISTEN 2>/dev/null); do kill "$p" 2>/dev/null; done   # servidor colgado
  PY="$IA/sony/venv/bin/python"; [ -x "$PY" ] || PY="/opt/homebrew/bin/python3"
  (cd "$PANEL" && nohup "$PY" -I servidor.py >> "$IA/logs/servidor.log" 2>&1 < /dev/null &)
  for i in $(seq 1 80); do curl -s -m1 -o /dev/null "http://127.0.0.1:8099/api/chat/estado" && break; sleep 0.3; done
  if ! curl -s -m2 -o /dev/null "http://127.0.0.1:8099/api/chat/estado"; then
    echo "$(date '+%F %T') ERROR: el panel no arranca" >> "$LOG"; exit 1
  fi
fi
if pgrep -f "user-data-dir=$PERFIL" >/dev/null && curl -s -m2 "http://127.0.0.1:8099/api/ventana/abierta" | grep -q '"abierta": true'; then
  echo "$(date '+%F %T') ventana ya abierta: al frente" >> "$LOG"; exit 3
fi
nohup "$CHROME" --user-data-dir="$PERFIL" --app="$URL" --no-first-run --no-default-browser-check >/dev/null 2>&1 < /dev/null &
echo "$(date '+%F %T') ventana abierta" >> "$LOG"
exit 0
