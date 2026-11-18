# Montaje de vídeos cortos (TikTok/Reels/Shorts) con ffmpeg, para Sony.
# Solo trabaja dentro de ~/Movies/videos-tiktok: lee de «originales» y escribe en «montajes».
# Textos encima del vídeo: los dibuja ~/IA/sony/herramientas/texto-png (este ffmpeg no trae drawtext).
import json, re, shutil, subprocess, tempfile, time
from pathlib import Path

BASE = Path.home() / "Movies" / "videos-tiktok"
ORIG, MONT, TRANS = BASE / "originales", BASE / "montajes", BASE / "transcripciones"
FFMPEG, FFPROBE = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg", shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
WHISPER = shutil.which("whisper") or "/opt/homebrew/bin/whisper"
TEXTO_PNG = Path.home() / "IA" / "sony" / "herramientas" / "texto-png"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
MAX_ESCENAS, MAX_SEG = 20, 180


def _carpetas():
    for c in (ORIG, MONT, TRANS):
        c.mkdir(parents=True, exist_ok=True)


def _ruta(nombre):
    """Archivo de entrada: nombre suelto (se busca en originales) o ruta dentro de videos-tiktok. Nada fuera."""
    n = str(nombre or "").strip().strip("'\"")
    if not n:
        raise ValueError("Falta el nombre del archivo.")
    p = Path(n).expanduser()
    if not p.is_absolute():
        p = (ORIG / n) if not (BASE / n).exists() else (BASE / n)
    p = p.resolve()
    if BASE.resolve() not in p.parents:
        raise ValueError(f"Solo puedo usar archivos de {BASE} (originales o montajes).")
    if not p.exists():
        raise ValueError(f"No existe «{n}». Mira la lista con video_lista.")
    return p


def _dur(p):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(p)],
                           capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout)
        v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
        return float(d.get("format", {}).get("duration") or 0), v.get("width"), v.get("height"), audio
    except Exception:
        return 0.0, None, None, False


def _seg(x):
    """'1:05' → 65, '12.5' → 12.5"""
    s = str(x if x is not None else "").strip()
    if not s:
        return None
    if ":" in s:
        m, _, r = s.rpartition(":")
        return _seg(m) * 60 + float(r) if m else float(r)
    return float(s)


def t_lista(a):
    _carpetas()
    filas = []
    for carpeta in (ORIG, MONT):
        for f in sorted(carpeta.iterdir()):
            if f.suffix.lower() in VIDEO_EXT:
                d, w, h, au = _dur(f)
                filas.append(f"- {carpeta.name}/{f.name} · {d:.1f} s · {w}x{h}{'' if au else ' · sin sonido'}")
            elif f.suffix.lower() in IMG_EXT:
                filas.append(f"- {carpeta.name}/{f.name} · imagen")
    if not filas:
        return (f"No hay vídeos todavía. El usuario tiene que meterlos en {ORIG} (por AirDrop desde el móvil, "
                "o en TikTok: Compartir → Guardar vídeo).")
    return "Vídeos e imágenes disponibles:\n" + "\n".join(filas)


def t_transcribir(a):
    """Saca lo que se dice en un vídeo, con tiempos (Whisper local). Se guarda y la segunda vez es instantáneo."""
    _carpetas()
    p = _ruta(a.get("archivo"))
    srt = TRANS / (p.stem + ".srt")
    if not srt.exists():
        if not Path(WHISPER).exists():
            return "No está instalado Whisper en este Mac."
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([WHISPER, str(p), "--model", "small", "--language", "es", "--output_format", "srt", "--output_dir", tmp, "--fp16", "False"],
                               capture_output=True, text=True, timeout=1800)
            hecho = next(Path(tmp).glob("*.srt"), None)
            if not hecho:
                return "No se pudo transcribir: " + (r.stderr or r.stdout)[-400:]
            shutil.copy(hecho, srt)
    bloques = re.split(r"\n\s*\n", srt.read_text(encoding="utf-8", errors="replace").strip())
    lineas = []
    for b in bloques:
        partes = b.strip().splitlines()
        if len(partes) >= 3:
            t = partes[1].replace(",", ".").split(" --> ")
            lineas.append(f"[{t[0][3:11]}–{t[1][3:11]}] {' '.join(partes[2:])}")
    return f"Transcripción de {p.name} (minutos:segundos):\n" + "\n".join(lineas)[:12000]


def _texto_png(texto, salida, tam=76):
    r = subprocess.run([str(TEXTO_PNG), texto, str(salida), "1080", str(tam)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not Path(salida).exists():
        raise RuntimeError("no pude dibujar el texto: " + (r.stderr or r.stdout)[:200])


def _escenas(a):
    e = a.get("escenas")
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except Exception:
            raise ValueError('«escenas» tiene que ser una lista JSON, por ejemplo [{"archivo": "partida.mp4", "desde": "0:05", "hasta": "0:09", "texto": "Gancho"}].')
    if not isinstance(e, list) or not e:
        raise ValueError("Falta la lista de escenas.")
    if len(e) > MAX_ESCENAS:
        raise ValueError(f"Máximo {MAX_ESCENAS} escenas.")
    return e


def t_montar(a):
    """Monta un vídeo vertical 1080x1920 a partir de trozos de vídeos o imágenes, con textos encima."""
    _carpetas()
    escenas = _escenas(a)
    nombre = re.sub(r"[^\w\-]+", "-", str(a.get("nombre") or "montaje").strip()).strip("-")[:60] or "montaje"
    salida = MONT / f"{nombre}.mp4"
    if salida.exists():
        salida = MONT / f"{nombre}-{time.strftime('%H%M%S')}.mp4"
    total = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); trozos = []
        for i, sc in enumerate(escenas, 1):
            if not isinstance(sc, dict):
                raise ValueError(f"La escena {i} no es válida.")
            p = _ruta(sc.get("archivo"))
            es_img = p.suffix.lower() in IMG_EXT
            dur_total, _, _, audio = (0.0, None, None, False) if es_img else _dur(p)
            desde = _seg(sc.get("desde")) or 0.0
            if es_img:
                dura = _seg(sc.get("duracion")) or 3.0
            else:
                hasta = _seg(sc.get("hasta"))
                hasta = min(hasta if hasta is not None else dur_total, dur_total or 1e9)
                dura = hasta - desde
                if dura <= 0.2:
                    raise ValueError(f"Escena {i}: «desde» ({desde}) y «hasta» ({hasta}) no dejan tiempo (el vídeo dura {dur_total:.1f} s).")
            total += dura
            if total > MAX_SEG:
                raise ValueError(f"El montaje pasaría de {MAX_SEG} s.")
            # encuadre vertical: si el original es horizontal, se pone encima de un fondo desenfocado del propio vídeo
            vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];"
                  "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[frente];"
                  "[fondo][frente]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p,setsar=1[v0]")
            entradas = (["-loop", "1", "-t", f"{dura:.3f}", "-i", str(p)] if es_img else ["-ss", f"{desde:.3f}", "-t", f"{dura:.3f}", "-i", str(p)])
            ultimo = "v0"
            texto = str(sc.get("texto") or "").strip()
            if texto:
                png = tmp / f"t{i}.png"; _texto_png(texto[:200], png, 84 if len(texto) < 40 else 66)
                entradas += ["-i", str(png)]
                y = {"arriba": "220", "centro": "(H-h)/2", "abajo": "H-h-380"}.get(str(sc.get("posicion") or "arriba"), "220")
                vf += f";[v0][1:v]overlay=(W-w)/2:{y}[v1]"; ultimo = "v1"
            # sonido: el del vídeo, o silencio si es imagen o no tiene
            if audio and not es_img:
                mapa_a = ["-map", "0:a:0"]
            else:
                entradas += ["-f", "lavfi", "-t", f"{dura:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
                mapa_a = ["-map", f"{2 if texto else 1}:a:0"]
            trozo = tmp / f"e{i:02d}.mp4"
            cmd = [FFMPEG, "-y", "-v", "error", *entradas, "-filter_complex", vf, "-map", f"[{ultimo}]", *mapa_a,
                   "-t", f"{dura:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", str(trozo)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0 or not trozo.exists():
                raise RuntimeError(f"Falló la escena {i}: {r.stderr[-400:]}")
            trozos.append(trozo)
        lista = tmp / "lista.txt"
        lista.write_text("".join(f"file '{t}'\n" for t in trozos), encoding="utf-8")
        r = subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(salida)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not salida.exists():
            raise RuntimeError("Falló al unir las escenas: " + r.stderr[-400:])
    d, w, h, _ = _dur(salida)
    return (f"Vídeo montado: {salida} ({d:.1f} s, {w}x{h}, {len(escenas)} escenas). "
            "Ábrelo para revisarlo antes de subirlo; no se ha publicado nada.")


HERRAMIENTAS = {
    "video_lista": (t_lista, False, "Ver los vídeos para montar",
                    {}, f"Lista los vídeos e imágenes del usuario para montajes ({ORIG}) y los montajes ya hechos, con duración y tamaño."),
    "video_transcribir": (t_transcribir, True, "Sacar lo que se dice en un vídeo",
                          {"archivo": "string"}, "Transcribe lo que se dice en un vídeo con tiempos (Whisper local; la primera vez tarda unos minutos y descarga el modelo). Sirve para elegir los mejores trozos."),
    "video_montar": (t_montar, True, "Montar un vídeo corto vertical",
                     {"nombre": "string", "escenas": "string"},
                     'Monta un vídeo vertical 1080x1920 para TikTok/Reels uniendo trozos. escenas = lista JSON: '
                     '[{"archivo": "partida.mp4", "desde": "0:05", "hasta": "0:09", "texto": "Gancho corto", "posicion": "arriba|centro|abajo"}, '
                     '{"archivo": "foto.jpg", "duracion": 3, "texto": "..."}]. Guarda en montajes/; NO publica.'),
}
