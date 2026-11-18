# Datos privados de esta casa (cámaras, red, cuentas). Viven en panel/privado.json, que NO se sube a GitHub.
# Copia privado.ejemplo.json a privado.json y rellénalo en tu equipo.
import json
from pathlib import Path

F = Path(__file__).with_name("privado.json")


def get(clave, defecto=None):
    try:
        return json.loads(F.read_text(encoding="utf-8")).get(clave, defecto)
    except (OSError, ValueError):
        return defecto
