// «IA Sony»: app de Mac que abre Sony. Al ser una app de verdad, el doble clic funciona
// aunque ya esté abierta (macOS le avisa con «reabrir»). Mientras vive, el panel de Sony sigue vivo;
// cuando cierras del todo la ventana de Sony (Chrome de Sony con Cmd+Q), para el panel y el modelo y se cierra.
import AppKit

let home = FileManager.default.homeDirectoryForCurrentUser.path
let perfil = home + "/IA/sony/chrome-app"
let script = home + "/IA/sony/lanzador/abrir-sony.sh"

func shell(_ args: [String]) -> Int32 {
    let p = Process(); p.executableURL = URL(fileURLWithPath: "/bin/bash"); p.arguments = args
    do { try p.run() } catch { return -1 }
    p.waitUntilExit(); return p.terminationStatus
}
func pidSony() -> pid_t? {
    let p = Process(); let out = Pipe()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep"); p.arguments = ["-f", "user-data-dir=" + perfil]; p.standardOutput = out
    do { try p.run() } catch { return nil }
    p.waitUntilExit()
    let txt = String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    return txt.split(separator: "\n").compactMap { pid_t($0) }.first
}
func pararTodo() {
    _ = shell(["-c", "for p in $(lsof -ti tcp:8099,8080,8091,8092 -sTCP:LISTEN 2>/dev/null); do kill $p 2>/dev/null; done"])
}

class Delegado: NSObject, NSApplicationDelegate {
    var ocupado = false
    var sinVentanaDesde: Date? = nil
    func abrirSony() {
        if ocupado { return }; ocupado = true
        DispatchQueue.global().async {
            let r = shell([script])
            DispatchQueue.main.async {
                self.ocupado = false
                if r == 3, let pid = pidSony(), let app = NSRunningApplication(processIdentifier: pid) {
                    app.activate()
                } else if r == 1 || r == -1 {
                    let a = NSAlert(); a.messageText = "Sony no ha podido arrancar"
                    a.informativeText = "Abre la Terminal y ejecuta:  ~/IA/sony/comprobar.sh\n(el detalle está en ~/IA/logs/servidor.log)"
                    NSApp.activate(ignoringOtherApps: true); a.runModal()
                }
            }
        }
    }
    func applicationDidFinishLaunching(_ n: Notification) {
        abrirSony()
        // Vigilante: si el Chrome de Sony lleva 40 s cerrado del todo, se para todo y la app se cierra.
        Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { _ in
            if self.ocupado { return }
            if pidSony() != nil { self.sinVentanaDesde = nil; return }
            if let d = self.sinVentanaDesde, Date().timeIntervalSince(d) > 35 { pararTodo(); NSApp.terminate(nil) }
            else if self.sinVentanaDesde == nil { self.sinVentanaDesde = Date() }
        }
    }
    // Doble clic en el icono (o clic en el Dock) con la app ya abierta
    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows f: Bool) -> Bool { abrirSony(); return false }
    func applicationWillTerminate(_ n: Notification) { pararTodo() }
}

let app = NSApplication.shared
let delegado = Delegado()
app.delegate = delegado
app.setActivationPolicy(.regular)
let menu = NSMenu(); let item = NSMenuItem(); menu.addItem(item)
let sub = NSMenu(); sub.addItem(withTitle: "Abrir Sony", action: #selector(Delegado.abrirMenu), keyEquivalent: "o")
sub.addItem(withTitle: "Cerrar Sony del todo", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
item.submenu = sub; app.mainMenu = menu
extension Delegado { @objc func abrirMenu() { abrirSony() } }
app.run()
