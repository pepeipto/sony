# Vista «nebulosa» del segundo cerebro. Se registra en servidor.py (ROUTES).
# Solo lectura de ~/segundo-cerebro. El grafo se cachea y se rehace si cambian las notas.
import threading, time
from urllib.parse import urlparse, parse_qs

import hacer_nebulosa as hn

_LOCK = threading.Lock()
_CACHE = {"firma": None, "grafo": None, "detalles": None, "comprobado": 0.0}


def _datos():
    with _LOCK:
        ahora = time.time()
        if _CACHE["grafo"] is None or ahora - _CACHE["comprobado"] > 10:
            f = hn.firma()
            _CACHE["comprobado"] = ahora
            if f != _CACHE["firma"] or _CACHE["grafo"] is None:
                _CACHE["grafo"], _CACHE["detalles"] = hn.construir()
                _CACHE["firma"] = f
        return _CACHE["grafo"], _CACHE["detalles"]


def vista(h):  # 3D (Three.js servido desde /static/vendor/three)
    h.static("nebulosa3d.html")


def vista_2d(h):  # version 2D (canvas) como alternativa ligera
    h.static("nebulosa.html")


def api(h):
    try:
        grafo, detalles = _datos()
    except Exception as e:  # p.ej. disco E: no disponible
        return h.send(503, {"error": f"no se pudo leer el segundo cerebro: {type(e).__name__}"})
    q = parse_qs(urlparse(h.path).query)
    if "nota" in q:
        d = detalles.get(q["nota"][0])
        return h.send(200, d) if d else h.send(404, {"error": "nota no encontrada"})
    h.send(200, grafo)


def a_galaxia(h):  # la nebulosa se retiró el 15/11/2026: todo va a la galaxia
    destino = "/galaxia-espiral-2d" if h.path.startswith("/nebulosa-2d") else "/galaxia-espiral"
    h.send_response(303); h.send_header("Location", destino); h.send_header("Content-Length", "0"); h.end_headers()


def register(routes):
    routes[("GET", "/nebulosa")] = a_galaxia
    routes[("GET", "/static/nebulosa-elite.html")] = a_galaxia
    routes[("GET", "/galaxia")] = vista
    routes[("GET", "/galaxia-espiral")] = vista
    routes[("GET", "/nebulosa-2d")] = a_galaxia
    routes[("GET", "/galaxia-espiral-2d")] = vista_2d
    routes[("GET", "/api/cerebro")] = api
