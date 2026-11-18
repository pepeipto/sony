#!/bin/zsh
# Copia de seguridad semanal de Sony al USB «ESD-USB». La lanza launchd los sábados a las 04:00 (o tú a mano).
# Guarda: segundo cerebro, skills, panel de Sony (código, ajustes y chats) y memoria. NO guarda: modelos, entorno Python,
# índice de búsqueda (se rehace solo), logs ni claves (el Llavero de macOS no se copia).
# Si el USB no está conectado, no hace nada y te avisa con una notificación.
# Conserva las 8 últimas copias creadas por este script; no toca ningún otro archivo del USB.
set -u
USB="/Volumes/ESD-USB"
DEST="$USB/copias-sony"
LOG="$HOME/IA/logs/copia-seguridad.log"
mkdir -p "${LOG:h}"

aviso() { /usr/bin/osascript -e "display notification \"$1\" with title \"Copia de seguridad de Sony\"" >/dev/null 2>&1; }
registro() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"; }

if [[ ! -d "$USB" ]]; then
  registro "SALTADA: el USB no está conectado"
  aviso "No se ha hecho: conecta el USB ESD-USB."
  exit 0
fi
ERR=$(touch "$USB/.sony-prueba" 2>&1)
if [[ $? -ne 0 ]]; then
  registro "SALTADA: no se puede escribir en el USB ($ERR). Falta el permiso de volúmenes externos para «Copia de Sony»."
  aviso "No se ha hecho: conecta el USB ESD-USB."
  exit 0
fi
rm -f "$USB/.sony-prueba"

mkdir -p "$DEST"
FECHA=$(date '+%Y-%m-%d')
TMP="$DEST/.copia-$FECHA.tar.gz.parcial"
FINAL="$DEST/copia-$FECHA.tar.gz"
cd "$HOME" || exit 1

/usr/bin/tar -czf "$TMP" \
  --exclude='IA/sony/panel/buscador' \
  --exclude='IA/sony/panel/__pycache__' \
  --exclude='IA/sony/panel/estado_conectores.json' \
  --exclude='IA/sony/venv' \
  --exclude='IA/sony/chrome-app' \
  --exclude='IA/sony/copias' \
  --exclude='IA/sony/panel-original-windows' \
  --exclude='.DS_Store' \
  segundo-cerebro IA/sony/skills IA/sony/skills-archivadas IA/sony/panel IA/sony/memoria-sony.json \
  IA/sony/herramientas IA/sony/lanzador IA/sony/instalar-skill.sh IA/sony/copia-seguridad.sh IA/sony/LEEME-MAC.md 2>>"$LOG"
RC=$?

if [[ $RC -ne 0 ]] || ! /usr/bin/tar -tzf "$TMP" >/dev/null 2>&1; then
  rm -f "$TMP"
  registro "ERROR: no se pudo crear o comprobar la copia (código $RC)"
  aviso "Ha fallado la copia. Mira ~/IA/logs/copia-seguridad.log"
  exit 1
fi
mv -f "$TMP" "$FINAL"
TAM=$(du -h "$FINAL" | cut -f1)

# se conservan las 8 últimas copias de este script (solo copia-AAAA-MM-DD.tar.gz de esta carpeta)
ls -1 "$DEST"/copia-????-??-??.tar.gz 2>/dev/null | sort | awk -v n=8 '{a[NR]=$0} END{for(i=1;i<=NR-n;i++) print a[i]}' | while read -r vieja; do rm -f "$vieja" && registro "borrada copia antigua ${vieja:t}"; done

registro "OK: ${FINAL:t} ($TAM)"
aviso "Copia hecha: ${FINAL:t} ($TAM)"
