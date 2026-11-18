# Voz de Sony en el Mac: oído (faster-whisper, local) y boca (Piper, local). Solo escucha en 127.0.0.1:8097.
# Lo arranca el panel (chat.voz_arrancar) la primera vez que se usa la voz. Sin internet: los modelos ya están en el disco.
#   POST /precargar           carga Whisper y Piper en memoria
#   POST /transcribir         audio Float32 mono 16 kHz (X-Formato: f32-16k) -> {"texto": "..."}
#   POST /hablar              {"texto": "..."} -> audio/wav
#   GET  /voces               [{"nombre": "..."}]
#   GET  /estado              {"whisper": bool, "piper": bool}
import io, json, re, sys, threading, time, wave
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import numpy as np

HOST, PORT = "127.0.0.1", 8097
AQUI = Path(__file__).resolve().parent
# nombre -> (motor, archivo o voz, hablante)
VOCES = {"Davefx (España)": ("piper", AQUI / "voces" / "es_ES-davefx-medium.onnx", None),
         "Sharvard hombre (España)": ("piper", AQUI / "voces" / "es_ES-sharvard-medium.onnx", 0),
         "Sharvard mujer (España)": ("piper", AQUI / "voces" / "es_ES-sharvard-medium.onnx", 1),
}
# Kokoro (más natural pero más lento) queda instalado pero fuera de la lista: El usuario eligió las tres de Piper (18/11).
OCULTAS = {"Kokoro Dora (mujer)": ("kokoro", "ef_dora", None), "Kokoro Alex (hombre)": ("kokoro", "em_alex", None)}
KOKORO = (AQUI / "kokoro" / "kokoro-v1.0.onnx", AQUI / "kokoro" / "voices-v1.0.bin")
VOZ_DEF = "Davefx (España)"
MODELO_WHISPER = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"  # ya descargado en ~/.cache/huggingface
LOG = Path.home() / "IA" / "logs" / "voz.log"

# Frases que Whisper se inventa con ruido o silencio (sale de los subtítulos de YouTube con los que se entrenó).
FANTASMAS = re.compile(
    r"(gracias por ver( el)? v[ií]deo|suscr[ií]bete|suscr[ií]banse|dale (a )?like|no olvides suscribirte|"
    r"subt[ií]tulos (realizados |hechos )?por|subtitulado por|amara\.org|gracias por (su|tu) atenci[oó]n|"
    r"nos vemos en el (pr[oó]ximo|siguiente) v[ií]deo)", re.I)
# Cortas que también puede decir el usuario de verdad: solo se tiran si Whisper duda de que haya voz.
DUDOSAS = re.compile(r"^\W*(gracias|muchas gracias|m[uú]sica|aplausos|risas|hasta la pr[oó]xima|m+|ah+|eh+)\W*$", re.I)

_w = {"whisper": None, "piper": {}, "kokoro": None}
_lock = threading.Lock()


def log(**d):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **d}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def whisper():
    with _lock:
        if _w["whisper"] is None:
            from faster_whisper import WhisperModel
            try:  # gráfica del Mac (Metal): ~0,6 s por frase en vez de ~2,7 s en el procesador
                _w["whisper"] = WhisperModel(MODELO_WHISPER, device="mps", compute_type="float16", local_files_only=True)
                _w["whisper"].transcribe(np.zeros(16000, dtype=np.float32), language="es")  # prueba: si Metal falla, al procesador
                log(evento="whisper", dispositivo="mps")
            except Exception as e:
                log(evento="whisper", dispositivo="cpu", motivo=f"{type(e).__name__}: {e}"[:200])
                _w["whisper"] = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8", cpu_threads=8, local_files_only=True)
        return _w["whisper"]


def voz_de(nombre):
    return VOCES.get(nombre) or OCULTAS.get(nombre) or VOCES[VOZ_DEF]


def piper(nombre):
    motor, ruta, _h = voz_de(nombre)
    if motor != "piper":
        motor, ruta, _h = VOCES[VOZ_DEF]
    with _lock:
        if ruta not in _w["piper"]:
            from piper import PiperVoice
            _w["piper"][ruta] = PiperVoice.load(str(ruta))
        return _w["piper"][ruta]


def kokoro():
    with _lock:
        if _w["kokoro"] is None:
            from kokoro_onnx import Kokoro
            _w["kokoro"] = Kokoro(str(KOKORO[0]), str(KOKORO[1]))
        return _w["kokoro"]


def precargar(nombre=VOZ_DEF):
    whisper()
    (kokoro() if voz_de(nombre)[0] == "kokoro" else piper(nombre))


def transcribir(audio):
    if audio.size < 16000 * 0.3:  # menos de 0,3 s: nada
        return ""
    if float(np.sqrt(np.mean(audio ** 2))) < 0.004:  # casi silencio
        return ""
    segs, _info = whisper().transcribe(
        audio, language="es", beam_size=1, vad_filter=True, vad_parameters={"threshold": 0.25, "min_silence_duration_ms": 500},
        condition_on_previous_text=False, no_speech_threshold=0.6, temperature=0.0)
    partes = []
    for s in segs:
        t = s.text.strip()
        limpio = FANTASMAS.sub("", t).strip(" .,;:!¡?¿") if t else ""
        if limpio != t and t:
            log(evento="quitado", caracteres=len(t))  # nunca se guarda lo que se oye
        t = limpio
        if not t or s.no_speech_prob > 0.6 or (DUDOSAS.search(t) and (s.no_speech_prob > 0.15 or s.avg_logprob < -0.7)):
            if t:
                log(evento="descartada", caracteres=len(t), no_speech=round(s.no_speech_prob, 2))
            continue
        partes.append(t)
    return " ".join(partes).strip()


def _silencio():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\0\0" * 2205)
    return buf.getvalue()


def _escala(v):
    """0 (lenta) … 5 (normal) … 10 (rápida) → length_scale de Piper (más bajo = más rápido)."""
    try:
        v = max(0.0, min(10.0, float(v)))
    except (TypeError, ValueError):
        v = 5.0
    return round(1.35 - v * 0.07, 3)


def hablar(texto, nombre, velocidad=5):
    texto = re.sub(r"\s+", " ", texto or "").strip()[:2000]
    if not re.search(r"\w", texto):  # sin nada pronunciable (solo signos): un silencio corto
        return _silencio()
    motor, v, hablante = voz_de(nombre)
    buf = io.BytesIO()
    try:
        with wave.open(buf, "wb") as w:
            if motor == "kokoro":
                audio, sr = kokoro().create(texto, voice=v, speed=round(1.35 / _escala(velocidad) * 0.74, 2), lang="es")
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            else:
                from piper import SynthesisConfig
                piper(nombre).synthesize_wav(texto, w, syn_config=SynthesisConfig(speaker_id=hablante, length_scale=_escala(velocidad)))
    except wave.Error:
        return _silencio()
    return buf.getvalue()


def _voz_elegida():
    try:  # la que el usuario tenga en Ajustes → Voz (solo se lee el nombre)
        return (json.loads((AQUI.parent / "panel" / "ajustes.json").read_text(encoding="utf-8")).get("voz") or {}).get("nombre") or VOZ_DEF
    except Exception:
        return VOZ_DEF


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, code, cuerpo, tipo="application/json; charset=utf-8"):
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", tipo); self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(cuerpo)

    def ok_origen(self):
        # Solo el panel de Sony (que reenvía sin Origin) o peticiones locales sin navegador. Nada de webs.
        if self.headers.get("Origin") or self.headers.get("Host", "") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            self.responder(403, {"error": "no permitido"}); return False
        return True

    def do_GET(self):
        if not self.ok_origen():
            return
        if self.path == "/voces":
            return self.responder(200, [{"nombre": n} for n in VOCES])
        if self.path == "/estado":
            return self.responder(200, {"whisper": _w["whisper"] is not None, "piper": bool(_w["piper"]) or _w["kokoro"] is not None})
        self.responder(404, {"error": "no existe"})

    def do_POST(self):
        if not self.ok_origen():
            return
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            n = -1
        if n < 0 or n > 60 * 16000 * 4 + 1024:
            return self.responder(413, {"error": "audio demasiado largo"})
        datos = self.rfile.read(n) if n else b""
        try:
            if self.path == "/precargar":
                threading.Thread(target=precargar, args=(_voz_elegida(),), daemon=True).start()
                return self.responder(200, {"ok": True})
            if self.path == "/transcribir":
                if self.headers.get("X-Formato") != "f32-16k":
                    return self.responder(400, {"error": "formato no soportado"})
                t0 = time.time()
                audio = np.frombuffer(datos[: len(datos) // 4 * 4], dtype=np.float32).copy()
                texto = transcribir(audio)
                log(evento="oido", segundos=round(time.time() - t0, 2), duracion=round(audio.size / 16000, 1), caracteres=len(texto))
                return self.responder(200, {"texto": texto})
            if self.path == "/hablar":
                d = json.loads(datos or b"{}")
                t0 = time.time(); wav = hablar(d.get("texto", ""), d.get("voz") or VOZ_DEF, d.get("velocidad", 5))
                log(evento="dicho", segundos=round(time.time() - t0, 2), caracteres=len(d.get("texto", "")))
                return self.responder(200, wav, "audio/wav")
        except Exception as e:
            log(evento="error", ruta=self.path, error=f"{type(e).__name__}: {e}"[:300])
            return self.responder(500, {"error": f"La voz ha fallado: {type(e).__name__}"})
        self.responder(404, {"error": "no existe"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), H)
    if "--precargar" in sys.argv:
        threading.Thread(target=precargar, args=(_voz_elegida(),), daemon=True).start()
    log(evento="arranque")
    srv.serve_forever()
