import Cocoa
import Foundation
import WebKit

/// Native Apple macOS WKWebView host for Zoe (Dorothy 3D Brain Centerpiece).
/// Compile on macOS with:
///   swiftc -O ZoeMacApp.swift -framework Cocoa -framework WebKit -o ZoeNative
final class ZoeLocalSchemeHandler: NSObject, WKURLSchemeHandler {
    private let desktopDir: URL
    private let obsDir: URL

    init(desktopDir: URL, obsDir: URL) {
        self.desktopDir = desktopDir.standardizedFileURL
        self.obsDir = obsDir.standardizedFileURL
        super.init()
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url else {
            task.didFailWithError(NSError(domain: "ZoeDesktop", code: 400))
            return
        }
        var rel = url.path
        while rel.hasPrefix("/") { rel.removeFirst() }

        let target: URL
        if rel.isEmpty || rel == "desktop.html" || rel == "desktop_home.html" {
            target = desktopDir.appendingPathComponent("desktop_home.html").standardizedFileURL
        } else if rel == "zoe-gem.png" {
            target = desktopDir.appendingPathComponent("icon.png").standardizedFileURL
        } else {
            if rel.hasPrefix("brain/") { rel = String(rel.dropFirst("brain/".count)) }
            if rel.isEmpty { rel = "index.html" }
            target = obsDir.appendingPathComponent(rel).standardizedFileURL
        }

        let allowedDesk = desktopDir.path.hasSuffix("/") ? desktopDir.path : desktopDir.path + "/"
        let allowedObs = obsDir.path.hasSuffix("/") ? obsDir.path : obsDir.path + "/"
        guard (target.path.hasPrefix(allowedDesk) || target.path.hasPrefix(allowedObs)),
              let data = try? Data(contentsOf: target) else {
            let notFound = HTTPURLResponse(url: url, statusCode: 404, httpVersion: "HTTP/1.1", headerFields: nil)!
            task.didReceive(notFound)
            task.didFinish()
            return
        }

        let mime = Self.mimeType(for: target.pathExtension.lowercased())
        let total = data.count
        if let rangeHdr = task.request.value(forHTTPHeaderField: "Range"),
           rangeHdr.lowercased().hasPrefix("bytes="), total > 0 {
            let spec = rangeHdr.dropFirst(6).split(separator: ",").first.map(String.init) ?? ""
            let parts = spec.split(separator: "-", omittingEmptySubsequences: false)
            let start = parts.count > 0 && !parts[0].isEmpty ? (Int(parts[0]) ?? 0) : 0
            let end = parts.count > 1 && !parts[1].isEmpty ? min(total - 1, Int(parts[1]) ?? (total - 1)) : (total - 1)
            if start >= 0 && start <= end && end < total {
                let slice = data.subdata(in: start..<(end + 1))
                let resp = HTTPURLResponse(url: url, statusCode: 206, httpVersion: "HTTP/1.1", headerFields: [
                    "Content-Type": mime,
                    "Content-Length": "\(slice.count)",
                    "Content-Range": "bytes \(start)-\(end)/\(total)",
                    "Accept-Ranges": "bytes"
                ])!
                task.didReceive(resp)
                task.didReceive(slice)
                task.didFinish()
                return
            }
        }

        let resp = HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1", headerFields: [
            "Content-Type": mime,
            "Content-Length": "\(total)",
            "Accept-Ranges": "bytes"
        ])!
        task.didReceive(resp)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}

    private static func mimeType(for ext: String) -> String {
        switch ext {
        case "html": return "text/html; charset=utf-8"
        case "js": return "application/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "mp4": return "video/mp4"
        default: return "application/octet-stream"
        }
    }
}

final class ZoeDesktopDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let res = Bundle.main.resourceURL ?? URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let desk = res.appendingPathComponent("desktop")
        let obs = res.appendingPathComponent("dorothy_brain_observatory")

        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(ZoeLocalSchemeHandler(desktopDir: desk, obsDir: obs), forURLScheme: "zoe-desktop")

        let rect = NSRect(x: 0, y: 0, width: 1360, height: 860)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Zoe · Dorothy 3D Brain"
        window.backgroundColor = NSColor(red: 7/255, green: 11/255, blue: 18/255, alpha: 1)
        window.center()

        let wv = WKWebView(frame: rect, configuration: cfg)
        wv.autoresizingMask = [.width, .height]
        wv.load(URLRequest(url: URL(string: "zoe-desktop://local/desktop_home.html")!))
        window.contentView = wv
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let delegate = ZoeDesktopDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
