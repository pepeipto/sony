// texto-png "texto" salida.png [ancho=1080] [tamaño=76]
// Dibuja un texto blanco con borde negro, centrado y partido en líneas, sobre fondo transparente (para los vídeos de Sony).
import AppKit
let a = CommandLine.arguments
guard a.count >= 3 else { print("uso: texto-png \"texto\" salida.png [ancho] [tamaño]"); exit(2) }
let texto = a[1], salida = a[2]
let ancho = CGFloat(Double(a.count > 3 ? a[3] : "1080") ?? 1080), tam = CGFloat(Double(a.count > 4 ? a[4] : "76") ?? 76)
let fuente = NSFont(name: "Arial-BoldMT", size: tam) ?? NSFont.boldSystemFont(ofSize: tam)
let par = NSMutableParagraphStyle(); par.alignment = .center; par.lineBreakMode = .byWordWrapping
func attrs(_ borde: Bool) -> [NSAttributedString.Key: Any] {
    var d: [NSAttributedString.Key: Any] = [.font: fuente, .paragraphStyle: par, .foregroundColor: NSColor.white]
    if borde { d[.strokeColor] = NSColor.black; d[.strokeWidth] = 14.0; d[.foregroundColor] = NSColor.black }
    return d
}
let margen: CGFloat = 70, w = ancho - 2 * margen
let caja = (texto as NSString).boundingRect(with: NSSize(width: w, height: 4000), options: [.usesLineFragmentOrigin], attributes: attrs(false))
let alto = ceil(caja.height) + 40
guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(ancho), pixelsHigh: Int(alto), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let r = NSRect(x: margen, y: 20, width: w, height: ceil(caja.height))
(texto as NSString).draw(with: r, options: [.usesLineFragmentOrigin], attributes: attrs(true))
(texto as NSString).draw(with: r, options: [.usesLineFragmentOrigin], attributes: attrs(false))
NSGraphicsContext.restoreGraphicsState()
guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
do { try png.write(to: URL(fileURLWithPath: salida)) } catch { print(error); exit(1) }
