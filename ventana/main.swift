// Sony: ventana propia de Mac (WKWebView) para el panel local http://127.0.0.1:8099/chat.
// Al abrir: enciende Ollama (si hace falta, con ~/IA/arrancar-ollama.sh) y el panel de Sony. Al cerrar: apaga solo el panel.
// Ollama NO se apaga: es compartido. Solo se navega a 127.0.0.1:8099; cualquier otro enlace se abre en Safari.
import AppKit
import WebKit

let home = FileManager.default.homeDirectoryForCurrentUser.path
let panelDir = home + "/IA/sony/panel"
let python = home + "/IA/sony/venv/bin/python"
let logDir = home + "/IA/logs"
let base = URL(string: "http://127.0.0.1:8099")!
let inicio = URL(string: "http://127.0.0.1:8099/chat")!

func vivo(_ url: String) -> Bool {
    var ok = false; let sem = DispatchSemaphore(value: 0)
    var req = URLRequest(url: URL(string: url)!); req.timeoutInterval = 1.5
    URLSession.shared.dataTask(with: req) { _, r, _ in ok = (r as? HTTPURLResponse)?.statusCode == 200; sem.signal() }.resume()
    sem.wait(); return ok
}
func apuntar(_ t: String) {
    let f = logDir + "/ventana-sony.log"; let l = "\(Date()) \(t)\n"
    if let h = FileHandle(forWritingAtPath: f) { h.seekToEndOfFile(); h.write(l.data(using: .utf8)!); try? h.close() }
    else { FileManager.default.createFile(atPath: f, contents: l.data(using: .utf8)) }
}
func lanzar(_ exe: String, _ args: [String], cwd: String? = nil, log: String? = nil) -> Process? {
    let p = Process(); p.executableURL = URL(fileURLWithPath: exe); p.arguments = args
    if let c = cwd { p.currentDirectoryURL = URL(fileURLWithPath: c) }
    p.standardInput = FileHandle.nullDevice
    if let l = log {
        FileManager.default.createFile(atPath: l, contents: nil, attributes: nil)  // no borra si existe
        if let h = FileHandle(forWritingAtPath: l) { h.seekToEndOfFile(); p.standardOutput = h; p.standardError = h }
    } else { p.standardOutput = FileHandle.nullDevice; p.standardError = FileHandle.nullDevice }
    do { try p.run(); return p } catch { return nil }
}

class Delegado: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, NSWindowDelegate {
    var ventana: NSWindow!
    var web: WKWebView!
    var panel: Process?

    func applicationDidFinishLaunching(_ n: Notification) {
        construirMenu()
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        cfg.mediaTypesRequiringUserActionForPlayback = []  // la voz de Sony suena sin tener que pulsar
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self; web.uiDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        ventana = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 780),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        ventana.title = "Sony"; ventana.contentView = web; ventana.delegate = self
        ventana.setFrameAutosaveName("VentanaSony"); if ventana.frame.origin == .zero { ventana.center() }
        web.loadHTMLString("<html><body style='background:#0d1b2a;color:#cfe3ff;font:20px -apple-system;display:flex;align-items:center;justify-content:center;height:90vh'>Despertando a Sony…</body></html>", baseURL: nil)
        ventana.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.global().async { self.arrancar() }
    }

    func arrancar() {
        try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
        if !vivo("http://127.0.0.1:11434/api/tags") {
            _ = lanzar("/bin/zsh", [home + "/IA/arrancar-ollama.sh"])
        }
        if !vivo("http://127.0.0.1:8099/api/chat/estado") {
            panel = lanzar("/usr/bin/arch", ["-arm64", python, "-I", "servidor.py"], cwd: panelDir, log: logDir + "/servidor.log")
        }
        for _ in 0..<120 { if vivo("http://127.0.0.1:8099/api/chat/estado") { break }; Thread.sleep(forTimeInterval: 0.5) }
        DispatchQueue.main.async {
            if vivo("http://127.0.0.1:8099/api/chat/estado") { self.web.load(URLRequest(url: inicio)) }
            else {
                let a = NSAlert(); a.messageText = "Sony no ha podido arrancar"
                a.informativeText = "Cierra Sony y vuelve a abrirla. Si sigue igual, el detalle está en ~/IA/logs/servidor.log"
                a.runModal()
            }
        }
    }

    func construirMenu() {
        let menu = NSMenu(); let app = NSMenuItem(); menu.addItem(app)
        let m = NSMenu(); m.addItem(withTitle: "Recargar", action: #selector(recargar), keyEquivalent: "r")
        m.addItem(withTitle: "Ocultar Sony", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        m.addItem(withTitle: "Salir de Sony", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); app.submenu = m
        let ed = NSMenuItem(); menu.addItem(ed); let e = NSMenu(title: "Edición")
        e.addItem(withTitle: "Deshacer", action: Selector(("undo:")), keyEquivalent: "z")
        e.addItem(withTitle: "Cortar", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        e.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        e.addItem(withTitle: "Pegar", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        e.addItem(withTitle: "Seleccionar todo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"); ed.submenu = e
        NSApp.mainMenu = menu
    }
    @objc func recargar() { web.reload() }

    // Solo el panel local dentro de la ventana; el resto, a Safari.
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = a.request.url else { return decisionHandler(.cancel) }
        if u.scheme == "about" || (u.host == "127.0.0.1" && u.port == 8099) {
            if a.shouldPerformDownload { return decisionHandler(.download) }
            return decisionHandler(.allow)
        }
        // Fuera del panel: solo si el usuario ha hecho clic en la ventana principal (nada automático desde iframes)
        let clic = a.navigationType == .linkActivated && (a.targetFrame?.isMainFrame ?? true) && (a.sourceFrame.isMainFrame)
        if clic && (u.scheme == "blob" || u.scheme == "data") { return decisionHandler(.download) }
        if clic && ["http", "https", "mailto"].contains(u.scheme ?? "") { NSWorkspace.shared.open(u) }
        decisionHandler(.cancel)
    }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) { apuntar("cargada: \(w.url?.absoluteString ?? "-")") }
    func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { apuntar("fallo: \(e.localizedDescription)") }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { apuntar("fallo al cargar: \(e.localizedDescription)") }
    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { apuntar("la página se cerró: se recarga"); w.reload() }
    func webView(_ w: WKWebView, decidePolicyFor r: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let propio = r.response.url?.host == "127.0.0.1" && r.response.url?.port == 8099
        decisionHandler(r.canShowMIMEType ? .allow : ((propio && r.isForMainFrame) ? .download : .cancel))
    }
    func webView(_ w: WKWebView, navigationAction: WKNavigationAction, didBecome d: WKDownload) { d.delegate = self }
    func webView(_ w: WKWebView, navigationResponse: WKNavigationResponse, didBecome d: WKDownload) { d.delegate = self }
    func download(_ d: WKDownload, decideDestinationUsing r: URLResponse, suggestedFilename nombre: String, completionHandler: @escaping (URL?) -> Void) {
        let dir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
        var destino = dir.appendingPathComponent((nombre as NSString).lastPathComponent); var i = 1
        while FileManager.default.fileExists(atPath: destino.path) {
            let s = (nombre as NSString).deletingPathExtension, x = (nombre as NSString).pathExtension
            destino = dir.appendingPathComponent("\(s) (\(i))" + (x.isEmpty ? "" : ".\(x)")); i += 1
        }
        completionHandler(destino)
    }
    func downloadDidFinish(_ d: WKDownload) { NSSound(named: "Glass")?.play() }

    // target=_blank y window.open
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url, a.sourceFrame.isMainFrame {
            if u.host == "127.0.0.1" && u.port == 8099 { w.load(a.request) }
            else if a.navigationType == .linkActivated && ["http", "https"].contains(u.scheme ?? "") { NSWorkspace.shared.open(u) }
        }
        return nil
    }
    // Micrófono: solo para el panel local
    func webView(_ w: WKWebView, requestMediaCapturePermissionFor o: WKSecurityOrigin, initiatedByFrame f: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(o.protocol == "http" && o.host == "127.0.0.1" && o.port == 8099 && f.isMainFrame && type == .microphone ? .grant : .deny)
    }
    // Adjuntar archivos
    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let o = NSOpenPanel(); o.allowsMultipleSelection = p.allowsMultipleSelection; o.canChooseDirectories = p.allowsDirectories; o.canChooseFiles = true
        o.beginSheetModal(for: ventana) { r in completionHandler(r == .OK ? o.urls : nil) }
    }
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.runModal(); completionHandler()
    }
    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "Aceptar"); a.addButton(withTitle: "Cancelar")
        completionHandler(a.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt m: String, defaultText d: String?, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = m; let t = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24)); t.stringValue = d ?? ""
        a.accessoryView = t; a.addButton(withTitle: "Aceptar"); a.addButton(withTitle: "Cancelar")
        completionHandler(a.runModal() == .alertFirstButtonReturn ? t.stringValue : nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }
    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows f: Bool) -> Bool { ventana.makeKeyAndOrderFront(nil); return true }
    func applicationWillTerminate(_ n: Notification) {
        // Apaga la voz de Sony (puerto 8097, solo si es la suya) y el panel (8099). Ollama sigue (lo comparte Hermes).
        _ = lanzar("/bin/bash", ["-c", "for p in $(lsof -ti tcp:8097 -sTCP:LISTEN 2>/dev/null); do ps -o command= -p $p | grep -q 'voz.py' && lsof -a -p $p -d cwd -Fn | grep -qx 'n'\"$HOME\"'/IA/sony/voz' && kill $p; done"])
        if let p = panel, p.isRunning { p.terminate() }
        else {  // panel arrancado por otra vía: solo se para si es el de Sony (su carpeta de trabajo es ~/IA/sony/panel)
            _ = lanzar("/bin/bash", ["-c", "for p in $(lsof -ti tcp:8099 -sTCP:LISTEN 2>/dev/null); do ps -o command= -p $p | grep -q 'servidor.py' && lsof -a -p $p -d cwd -Fn | grep -qx 'n'\"$HOME\"'/IA/sony/panel' && kill $p; done"]); Thread.sleep(forTimeInterval: 0.7) }
    }
}

let app = NSApplication.shared
let d = Delegado(); app.delegate = d
app.setActivationPolicy(.regular)
app.run()
