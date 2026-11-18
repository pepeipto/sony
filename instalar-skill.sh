#!/bin/zsh
# Instala una skill de skills.sh en Sony (~/IA/sony/skills/externas), SOLO cuando el usuario lo ejecuta a mano.
# Sony no puede ejecutarlo: su terminal tiene prohibido tocar ~/IA/sony (no se modifica a sí misma).
# Uso:  ~/IA/sony/instalar-skill.sh dueño/repositorio@nombre-skill
set -e
setopt nullglob
PKG="$1"
if [[ "$PKG" != */*@* ]]; then
  echo "Uso: $0 dueño/repositorio@nombre-skill   (por ejemplo social-media-skills/skills@hook-writer)"; exit 1
fi
REPO="${PKG%@*}"; SKILL="${PKG##*@}"
if [[ ! "$REPO" =~ '^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$' || ! "$SKILL" =~ '^[A-Za-z0-9._-]+$' ]]; then
  echo "Nombre no válido."; exit 1
fi
DEST="$HOME/IA/sony/skills/externas/$SKILL"
if [[ -e "$DEST" ]]; then echo "Ya existe: $DEST"; exit 1; fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "Descargando https://github.com/$REPO …"
if [[ -n "$2" && -d "$2" ]]; then  # carpeta ya descargada (la usa Claude al instalar un paquete entero)
  cp -R "$2" "$TMP/repo"
else
  git clone --quiet --depth 1 "https://github.com/$REPO.git" "$TMP/repo"
fi

DIR=""
for f in "$TMP"/repo/**/SKILL.md; do
  d="${f:h}"
  if [[ "${d:t}" == "$SKILL" ]] || grep -qE "^name:[[:space:]]*['\"]?${SKILL}['\"]?[[:space:]]*\$" "$f"; then DIR="$d"; break; fi
done
if [[ -z "$DIR" ]]; then echo "No encuentro la skill «$SKILL» en $REPO."; exit 1; fi

echo; echo "===== SKILL.md (primeras 40 líneas) ====="
head -40 "$DIR/SKILL.md"
echo "=========================================="
OTROS=("$DIR"/**/*(.))
echo; echo "Archivos que trae:"
for f in $OTROS; do echo "  ${f#$DIR/}"; done
SCRIPTS=("$DIR"/**/*.(sh|py|js|ts|mjs|cjs|rb|ps1|bat|command)(.))
if (( ${#SCRIPTS} )); then
  echo; echo "⚠️  Trae ${#SCRIPTS} script(s). Revísalos antes de pedirle a Sony que los use."
fi
if [[ -n "$SONY_CONFIRMADO" ]]; then r=s; else echo; read "r?¿Instalarla en Sony? (s/N) "; fi
[[ "$r" == [sS] ]] || { echo "Cancelado. No se ha instalado nada."; exit 0; }

mkdir -p "${DEST:h}"
cp -R "$DIR" "$DEST"
python3 -I - "$SKILL" "$DEST/SKILL.md" "$PKG" <<'PY'
import sys, pathlib
import re
nombre, skill_md, pkg = sys.argv[1], sys.argv[2], sys.argv[3]
desc, lin = "", pathlib.Path(skill_md).read_text(encoding="utf-8", errors="replace").splitlines()
for i, l in enumerate(lin):
    m = re.match(r"description:\s*(.*)$", l)
    if m:
        v = m.group(1).strip()
        if v in ("", ">", ">-", "|", "|-"):  # descripción en varias líneas (YAML)
            partes = []
            for x in lin[i + 1:]:
                if not x.startswith((" ", "\t")): break
                partes.append(x.strip())
            v = " ".join(partes)
        desc = v.strip("'\"")[:150]
        break
p = pathlib.Path.home() / "IA/sony/skills/INDICE.md"
lineas = p.read_text(encoding="utf-8").splitlines()
nueva = f"- {nombre}: {desc} (de {pkg}) [pendiente de prueba]"
ini = next(i for i, l in enumerate(lineas) if l.startswith("## Externas"))
pos = ini + 1
for i in range(ini + 1, len(lineas)):
    if lineas[i].startswith("## "): break
    if lineas[i].startswith("- "): pos = i + 1
lineas.insert(pos, nueva)
p.write_text("\n".join(lineas) + "\n", encoding="utf-8")
PY
echo "Instalada en $DEST y añadida al índice como «pendiente de prueba»."
echo "Sony la verá en el próximo mensaje (Ajustes → Skills para activarla o desactivarla)."
