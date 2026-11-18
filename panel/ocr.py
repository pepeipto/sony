# OCR de Sony (15/11/2026): lee texto de PDF escaneados y de imágenes.
# - RapidOCR 3 (onnxruntime, modelo latino PP-OCRv3) en el PROCESADOR: 0 MB de VRAM. Se carga solo la primera vez que hace falta y se libera tras 10 min sin uso.
# - pypdfium2 para pasar las páginas del PDF a imagen. Nada arranca con Windows.
import io, threading, time

_m = {"motor": None, "t": 0.0}
_lock = threading.Lock()
MAX_PAGINAS = 40


def _motor():
    with _lock:
        if _m["motor"] is None:
            import logging
            from rapidocr import RapidOCR, LangRec
            logging.getLogger("RapidOCR").setLevel(logging.WARNING)
            _m["motor"] = RapidOCR(params={"Rec.lang_type": LangRec.LATIN})  # modelo latino (español con tildes y espacios)
            threading.Thread(target=_liberar_si_no_se_usa, daemon=True).start()
        _m["t"] = time.time()
        return _m["motor"]


def _liberar_si_no_se_usa():
    while True:
        time.sleep(60)
        with _lock:
            if _m["motor"] is not None and time.time() - _m["t"] > 600:
                _m["motor"] = None  # libera la RAM del OCR
                return


def _lineas(r):
    if r is None or not getattr(r, "txts", None):
        return ""
    filas = sorted(zip(r.boxes, r.txts, r.scores), key=lambda x: (round(x[0][0][1] / 12), x[0][0][0]))  # arriba→abajo
    return "\n".join(t for _, t, s in filas if s >= 0.3)


def imagen(datos):
    """Texto de una imagen (bytes)."""
    return _lineas(_motor()(datos))


def pdf(datos, max_paginas=MAX_PAGINAS):
    """Texto de un PDF escaneado (cada página se pasa a imagen y se lee). Devuelve (texto, paginas_leidas, total)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(datos)
    total = len(doc); partes = []
    for i in range(min(total, max_paginas)):
        img = doc[i].render(scale=2).to_pil()
        buf = io.BytesIO(); img.save(buf, format="PNG")
        t = imagen(buf.getvalue())
        if t.strip():
            partes.append(f"[Página {i + 1}]\n{t}")
    return "\n\n".join(partes), min(total, max_paginas), total
