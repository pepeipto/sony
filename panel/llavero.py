# Llavero de macOS (Keychain) sin dependencias: Security.framework vía ctypes.
# Las claves y contraseñas se guardan SOLO aquí, nunca en archivos, logs ni el chat.
# Interfaz compatible con la antigua del Administrador de credenciales de Windows:
#   cred_guardar(id, usuario, secreto) / cred_leer(id) -> (usuario, secreto) / cred_borrar(id)
import ctypes, ctypes.util, json

_sec = ctypes.CDLL(ctypes.util.find_library("Security"))
_cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
_OK, _DUP, _NOTFOUND = 0, -25299, -25300
_CUENTA = b"sony"  # cuenta fija; el servicio distingue cada credencial

_sec.SecKeychainAddGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p,
                                               ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_sec.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p,
                                                ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
_sec.SecKeychainItemModifyAttributesAndData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
_sec.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_sec.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
_cf.CFRelease.argtypes = [ctypes.c_void_p]


def _servicio(cid):
    return f"IA Sony/{cid}".encode()


def _buscar(cid):
    svc = _servicio(cid); n = ctypes.c_uint32(0); datos = ctypes.c_void_p(); item = ctypes.c_void_p()
    st = _sec.SecKeychainFindGenericPassword(None, len(svc), svc, len(_CUENTA), _CUENTA, ctypes.byref(n), ctypes.byref(datos), ctypes.byref(item))
    return st, n, datos, item


def cred_guardar(cid, usuario, secreto):
    blob = json.dumps({"u": usuario, "s": secreto}).encode()
    svc = _servicio(cid); item = ctypes.c_void_p()
    st = _sec.SecKeychainAddGenericPassword(None, len(svc), svc, len(_CUENTA), _CUENTA, len(blob), blob, ctypes.byref(item))
    if st == _DUP:
        st, n, datos, it = _buscar(cid)
        if st == _OK:
            _sec.SecKeychainItemFreeContent(None, datos)
            st = _sec.SecKeychainItemModifyAttributesAndData(it, None, len(blob), blob)
            _cf.CFRelease(it)
    elif item.value:
        _cf.CFRelease(item)
    if st != _OK:
        raise OSError(f"No se pudo guardar en el Llavero (código {st})")


def cred_leer(cid):
    st, n, datos, item = _buscar(cid)
    if st != _OK:
        return None, None
    try:
        d = json.loads(ctypes.string_at(datos, n.value).decode())
        return d.get("u"), d.get("s")
    finally:
        _sec.SecKeychainItemFreeContent(None, datos)
        if item.value:
            _cf.CFRelease(item)


def cred_borrar(cid):
    st, n, datos, item = _buscar(cid)
    if st == _OK:
        _sec.SecKeychainItemFreeContent(None, datos)
        _sec.SecKeychainItemDelete(item)
        _cf.CFRelease(item)


if __name__ == "__main__":  # autoprueba con un valor ficticio, que se borra al terminar
    cred_guardar("_prueba", "usuario-prueba", "valor-ficticio-123")
    assert cred_leer("_prueba") == ("usuario-prueba", "valor-ficticio-123"), "lectura distinta"
    cred_guardar("_prueba", "usuario-prueba", "valor-ficticio-456")
    assert cred_leer("_prueba")[1] == "valor-ficticio-456", "no actualiza"
    cred_borrar("_prueba")
    assert cred_leer("_prueba") == (None, None), "no borra"
    print("Llavero OK")
