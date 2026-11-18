# Herramienta de Sony: crear una imagen con FLUX.1 schnell (ComfyUI local, ~/IA\imagen).
# Regla del usuario: NUNCA dos modelos a la vez. Por eso: se descarga el modelo de chat, se espera a que la gráfica
# quede libre, se genera, se cierra ComfyUI, se espera otra vez y se vuelve a cargar el modelo de chat. Siempre con tarjeta.
import base64, json, subprocess, time, urllib.request, uuid
from pathlib import Path

import chat

COMFY_DIR = Path(r"~/IA\imagen\ComfyUI_windows_portable")
COMFY_URL = "http://127.0.0.1:8188"
SALIDA_COMFY = COMFY_DIR / "ComfyUI" / "output"
CAPTURAS = chat.BASE / "adjuntos" / "_pantalla"  # misma carpeta que sirve /api/agente/captura/
LOGS = Path(r"~/IA\logs")
NO_WINDOW = 0x08000000


def _gpu():
    r = subprocess.run(["nvidia-smi", "--query-gpu=power.draw,power.limit,temperature.gpu", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10)
    if r.returncode != 0 or "lost" in r.stdout.lower():
        raise RuntimeError("la gráfica no responde")
    w, lim, t = [float(x) for x in r.stdout.strip().split(",")]
    return w, lim, t


def _comfy_vivo():
    try:
        urllib.request.urlopen(COMFY_URL + "/system_stats", timeout=2).read(); return True
    except Exception:
        return False


def _flujo(texto, semilla):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": texto, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                                                   "seed": semilla, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "sony"}},
    }


def generar(descripcion):
    """Genera la imagen con el modelo de chat YA descargado. Devuelve la ruta del PNG."""
    w, lim, t = _gpu()
    import vigilancia_gpu
    if lim > vigilancia_gpu.LIMITE_OBJETIVO_W + 10:
        raise RuntimeError(f"la gráfica no tiene su límite de {vigilancia_gpu.LIMITE_OBJETIVO_W} W ({lim:.0f} W)")
    proc = None
    try:
        if not _comfy_vivo():
            proc = subprocess.Popen([str(COMFY_DIR / "python_embeded" / "python.exe"), "-s", "ComfyUI\\main.py", "--windows-standalone-build",
                                     "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch"], cwd=str(COMFY_DIR),
                                    stdout=open(LOGS / "comfyui.log", "ab"), stderr=open(LOGS / "comfyui-err.log", "ab"), creationflags=NO_WINDOW)
            fin = time.time() + 180
            while time.time() < fin and not _comfy_vivo():
                time.sleep(2)
            if not _comfy_vivo():
                raise RuntimeError("ComfyUI no arrancó")
        pid = json.loads(urllib.request.urlopen(urllib.request.Request(
            COMFY_URL + "/prompt", data=json.dumps({"prompt": _flujo(descripcion, int(time.time()) % 100000), "client_id": uuid.uuid4().hex}).encode(),
            headers={"Content-Type": "application/json"}), timeout=30).read())["prompt_id"]
        fin = time.time() + 600
        while time.time() < fin:
            time.sleep(1)
            w, lim, t = _gpu()
            if w > vigilancia_gpu.LIMITE_W:
                raise RuntimeError(f"la gráfica pasó de {vigilancia_gpu.LIMITE_W} W ({w:.0f} W): se para")
            h = json.loads(urllib.request.urlopen(COMFY_URL + "/history/" + pid, timeout=10).read())
            if pid in h:
                img = h[pid]["outputs"]["7"]["images"][0]
                CAPTURAS.mkdir(parents=True, exist_ok=True)
                dst = CAPTURAS / f"imagen-{time.strftime('%Y%m%d-%H%M%S')}.png"
                dst.write_bytes((SALIDA_COMFY / img.get("subfolder", "") / img["filename"]).read_bytes())
                return dst
        raise RuntimeError("la imagen tardó demasiado")
    finally:
        if proc:  # cerramos ComfyUI (libera la VRAM)
            proc.terminate()
            try: proc.wait(20)
            except Exception: proc.kill()


def t_imagen(a):
    descripcion = (a.get("descripcion") or "").strip()
    if not descripcion:
        return "Falta la descripción de la imagen."
    modelo = chat._proc.get("modelo") or "rapido"
    chat.descargar()                       # 1) fuera el modelo de chat
    if not chat.esperar_grafica_libre(max_s=90):
        chat.cargar(modelo)
        return "La gráfica no se ha quedado libre: no genero la imagen (regla: nunca dos modelos a la vez)."
    error = None
    try:
        f = generar(descripcion)           # 2) genera y cierra ComfyUI
    except Exception as e:
        f = None; error = str(e)
    chat.esperar_grafica_libre(max_s=90)   # 3) vuelve el modelo de chat
    chat.cargar(modelo)
    for _ in range(600):
        if chat.llama_listo():
            break
        time.sleep(0.5)
    if not f:
        return f"No he podido crear la imagen: {error}"
    return {"imagen": "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode(), "archivo": f.name,
            "texto": f"Imagen creada y guardada en {f} (la imagen va a continuación).",
            "intro": "Esta es la imagen que acabas de crear con FLUX:"}


HERRAMIENTAS = {
    "imagen_crear": (t_imagen, True, "Crear una imagen con FLUX (el chat se pausa ~1 minuto)",
                     {"descripcion": "string"},
                     "Crea una imagen con FLUX en el PC del usuario. descripcion: EN INGLÉS, detallada (tema, estilo, luz, colores). "
                     "Tarda ~1-2 minutos porque el modelo de chat se descarga mientras tanto. Pide tarjeta."),
}
