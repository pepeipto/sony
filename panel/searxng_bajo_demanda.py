# Búsqueda web de Sony: SearXNG en Docker (solo 127.0.0.1:8888), arrancado BAJO DEMANDA.
# - Nada arranca con Windows. Docker Desktop y el contenedor se encienden la primera vez que Sony busca.
# - Tras 20 minutos sin búsquedas se para el contenedor y se cierra Docker Desktop (libera RAM).
import subprocess, threading, time, urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8888"
DOCKER_DESKTOP = Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
INACTIVO_S = 20 * 60
NO_WINDOW = 0x08000000
_estado = {"ultimo_uso": 0.0, "lo_arranque_yo": False}
_lock = threading.Lock()


def _vivo(timeout=2):
    try:
        with urllib.request.urlopen(URL + "/healthz", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)


def _docker_listo():
    try:
        return _docker("info", "--format", "{{.ServerVersion}}", timeout=15).returncode == 0
    except Exception:
        return False


def asegurar(espera_max=150):
    """Devuelve True si SearXNG responde (arrancándolo si hace falta)."""
    _estado["ultimo_uso"] = time.time()
    if _vivo():
        return True
    with _lock:
        if _vivo():
            return True
        if not _docker_listo():
            if not DOCKER_DESKTOP.exists():
                return False
            subprocess.Popen([str(DOCKER_DESKTOP)], creationflags=NO_WINDOW)
            fin = time.time() + espera_max
            while time.time() < fin and not _docker_listo():
                time.sleep(3)
            if not _docker_listo():
                return False
        _docker("start", "searxng")
        _estado["lo_arranque_yo"] = True
        fin = time.time() + 60
        while time.time() < fin:
            if _vivo():
                return True
            time.sleep(1)
    return False


def _vigilar():
    while True:
        time.sleep(60)
        try:
            if _estado["lo_arranque_yo"] and _estado["ultimo_uso"] and time.time() - _estado["ultimo_uso"] > INACTIVO_S:
                _docker("stop", "searxng", timeout=60)
                try:
                    _docker("desktop", "stop", timeout=120)  # cierra Docker Desktop y su máquina virtual
                except Exception:
                    pass
                _estado.update(lo_arranque_yo=False, ultimo_uso=0.0)
        except Exception:
            pass


def register(R):
    if _vivo():  # si ya estaba encendido al arrancar el panel, también se apaga solo tras 20 min sin uso
        _estado.update(lo_arranque_yo=True, ultimo_uso=time.time())
    threading.Thread(target=_vigilar, daemon=True, name="searxng-vigilancia").start()
