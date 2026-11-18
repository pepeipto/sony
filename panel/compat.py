# Rutas y utilidades comunes de Sony en macOS (sustituye a las constantes rutas del PC).
import re, subprocess, time
from pathlib import Path

# HTTPS con los certificados del Mac (Llavero del sistema). El Python de python.org no trae certificados propios
# y sin esto Google, la búsqueda web, etc. fallan con CERTIFICATE_VERIFY_FAILED. La verificación sigue activada.
try:
    import sys as _s0
    for _p0 in (Path.home() / "IA" / "sony" / "venv" / "lib").glob("python3*/site-packages"):
        if str(_p0) not in _s0.path:
            _s0.path.append(str(_p0))
    import truststore as _ts
    _ts.inject_into_ssl()
except Exception:
    pass
from pathlib import Path

HOME = Path.home()
IA = HOME / "IA"
LOGS = IA / "logs"
MODELOS = IA / "modelos"
CEREBRO = HOME / "segundo-cerebro"
SKILLS = IA / "sony" / "skills"
LLAMA = Path("/opt/homebrew/bin/llama-server")
NO_WINDOW = 0  # en macOS no hay ventanas de consola
LOGS.mkdir(parents=True, exist_ok=True)


def memoria():
    """(total_gb, disponible_gb). Disponible = libre + inactiva + especulativa + purgable (lo que macOS puede ceder)."""
    try:
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout.strip())
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        pag = int(re.search(r"page size of (\d+) bytes", out).group(1))
        n = lambda k: int(re.search(rf"{k}:\s+(\d+)", out).group(1))
        disp = (n("Pages free") + n("Pages inactive") + n("Pages speculative") + n("Pages purgeable")) * pag
        g = 1024 ** 3
        return total / g, disp / g
    except Exception:
        return 0.0, 0.0


def rotar_logs(max_mb=5):
    """Al arrancar: si un log pasa de max_mb, se guarda como .1 (se conserva una copia anterior) y se empieza de nuevo. Evita que crezcan sin fin."""
    try:
        for f in LOGS.glob("*"):
            if f.is_file() and f.suffix in (".log", ".jsonl") and f.stat().st_size > max_mb * 1024 * 1024:
                viejo = f.with_suffix(f.suffix + ".1")
                if viejo.exists():
                    viejo.unlink()
                f.rename(viejo)
    except Exception:
        pass


# Paquetes del entorno aislado de Sony (anthropic, numpy): disponibles para todo el panel aunque se arranque con python3 -I
import sys as _sys
for _p in (IA / "sony" / "venv" / "lib").glob("python3*/site-packages"):  # VENV_SITE
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
