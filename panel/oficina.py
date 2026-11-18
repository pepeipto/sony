# Office de verdad para Sony (16/11/2026, mejora nº 3 elegida por el usuario): Excel (.xlsx con fórmulas) y Word (.docx).
# Usa Excel y Word de Office 2024 por COM, sin abrir ventana. No instala nada. Guardar siempre pide tarjeta (perm True).
import json, subprocess, tempfile, os
from pathlib import Path

NO_WINDOW = 0x08000000

_PS_EXCEL = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$d = Get-Content -Raw -Encoding UTF8 $args[0] | ConvertFrom-Json
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Add(); $ws = $wb.Worksheets.Item(1)
  if ($d.titulo) { $ws.Name = ([string]$d.titulo).Substring(0, [Math]::Min(31, ([string]$d.titulo).Length)) }
  $f = 0; $nform = 0
  foreach ($fila in $d.filas) {
    $f++; $c = 0
    foreach ($v in $fila) {
      $c++; $celda = $ws.Cells.Item($f, $c)
      if ($v -is [string] -and $v.StartsWith('=')) {
        try { $celda.Formula = $v } catch { $celda.FormulaLocal = $v }
        if (([string]$celda.Text).StartsWith('#')) { try { $celda.FormulaLocal = $v } catch {} }  # p. ej. =SUMA(...) en español
        $nform++
      } elseif ($v -is [int] -or $v -is [long] -or $v -is [double] -or $v -is [decimal]) { $celda.Value2 = [double]$v
      } elseif ($v -is [bool]) { $celda.Value2 = [bool]$v
      } elseif ($null -ne $v) { $celda.Value2 = [string]$v }
    }
  }
  $ws.Rows.Item(1).Font.Bold = $true
  $null = $ws.UsedRange.Columns.AutoFit()
  $wb.SaveAs($d.ruta, 51)
  $wb.Close($false)
  # comprobación: se vuelve a abrir y se leen los valores calculados
  $wb2 = $xl.Workbooks.Open($d.ruta); $ws2 = $wb2.Worksheets.Item(1); $u = $ws2.UsedRange
  $errores = 0; $muestras = @()
  for ($i = 1; $i -le $u.Rows.Count; $i++) { for ($j = 1; $j -le $u.Columns.Count; $j++) {
    $cel = $ws2.Cells.Item($i, $j)
    if ($cel.HasFormula) { $t = [string]$cel.Text; if ($t.StartsWith('#')) { $errores++ }; if ($muestras.Count -lt 4) { $muestras += ($cel.Address(0,0) + ' ' + $cel.Formula + ' = ' + $t) } }
  } }
  $nf = [int]$u.Rows.Count; $nc = [int]$u.Columns.Count
  $wb2.Close($false)
  [pscustomobject]@{ filas = $nf; columnas = $nc; formulas = $nform; errores = $errores; muestras = $muestras } | ConvertTo-Json -Compress
} finally { $xl.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
"""

_PS_WORD = r"""
$ErrorActionPreference = 'Stop'
$d = Get-Content -Raw -Encoding UTF8 $args[0] | ConvertFrom-Json
$w = New-Object -ComObject Word.Application
$w.Visible = $false; $w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Add(); $sel = $w.Selection
  foreach ($linea in ([string]$d.texto -split "`n")) {
    $l = $linea.TrimEnd("`r")
    if ($l -match '^# (.*)') { $sel.Style = $doc.Styles.Item(-2); $sel.TypeText($matches[1]) }
    elseif ($l -match '^## (.*)') { $sel.Style = $doc.Styles.Item(-3); $sel.TypeText($matches[1]) }
    elseif ($l -match '^[-*] (.*)') { $sel.Style = $doc.Styles.Item(-49); $sel.TypeText($matches[1]) }
    else { $sel.Style = $doc.Styles.Item(-1); $sel.TypeText($l) }
    $sel.TypeParagraph()
  }
  $doc.SaveAs2($d.ruta, 16); $n = $doc.Paragraphs.Count; $doc.Close($false)
  [pscustomobject]@{ parrafos = $n } | ConvertTo-Json -Compress
} finally { $w.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($w) }
"""


def _correr(script, datos, extension):
    ruta = Path(str(datos.get("ruta") or "").strip().strip('"'))
    if not ruta.is_absolute():
        return None, "La ruta tiene que ser completa (por ejemplo ~/segundo-cerebro\\sony\\practicas\\archivo" + extension + ")."
    if ruta.suffix.lower() != extension:
        ruta = ruta.with_suffix(extension)
    if not ruta.parent.exists():
        return None, f"No existe la carpeta {ruta.parent}."
    datos = {**datos, "ruta": str(ruta)}
    with tempfile.TemporaryDirectory() as tmp:
        fj = Path(tmp) / "datos.json"; fj.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        fp = Path(tmp) / "hacer.ps1"; fp.write_text(script, encoding="utf-8-sig")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(fp), str(fj)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=NO_WINDOW)
    if r.returncode != 0 or not ruta.exists():
        return None, "Office dio un error: " + (r.stderr or r.stdout).strip()[-400:]
    try:
        return ruta, json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return ruta, {}


def t_excel(a):
    filas = a.get("filas")
    if isinstance(filas, str):
        try:
            filas = json.loads(filas)
        except Exception:
            return "«filas» tiene que ser una lista de filas, por ejemplo [[\"Categoría\",\"Previsto\"],[\"Luz\",80]]."
    if not filas or not all(isinstance(f, list) for f in filas):
        return "«filas» tiene que ser una lista de filas (cada fila, una lista de celdas)."
    ruta, info = _correr(_PS_EXCEL, {"ruta": a.get("ruta"), "titulo": a.get("titulo") or "", "filas": filas}, ".xlsx")
    if ruta is None:
        return info
    txt = (f"Excel guardado en {ruta}: {info.get('filas')} filas × {info.get('columnas')} columnas, {info.get('formulas', 0)} fórmulas"
           + (f", {info['errores']} con ERROR (revísalas)" if info.get("errores") else ", todas calculan bien") + ".")
    if info.get("muestras"):
        txt += "\nComprobado al reabrirlo: " + "; ".join(info["muestras"] if isinstance(info["muestras"], list) else [info["muestras"]])
    return txt


def t_word(a):
    texto = str(a.get("texto") or "")
    if not texto.strip():
        return "Falta el texto del documento."
    ruta, info = _correr(_PS_WORD, {"ruta": a.get("ruta"), "texto": texto}, ".docx")
    if ruta is None:
        return info
    return f"Word guardado en {ruta} ({info.get('parrafos', '?')} párrafos)."


HERRAMIENTAS = {
    "excel_crear": (t_excel, True, "Crear un Excel (.xlsx) con fórmulas", {"ruta": "string", "filas": "array", "titulo": "string"},
                    "Crea un Excel .xlsx de verdad con Excel de Office (sin ventana). filas = lista de filas; cada fila, lista de celdas "
                    "(texto, número o fórmula que empieza por «=», en inglés y con comas, p. ej. \"=B2-C2\" o \"=SUM(B2:B9)\"). "
                    "La primera fila va en negrita. titulo = nombre de la hoja (opcional). Al guardar lo reabre y comprueba que las fórmulas calculan."),
    "word_crear": (t_word, True, "Crear un documento de Word (.docx)", {"ruta": "string", "texto": "string"},
                   "Crea un .docx con Word de Office (sin ventana). texto: «# » título, «## » subtítulo, «- » viñeta; el resto, párrafos."),
}
