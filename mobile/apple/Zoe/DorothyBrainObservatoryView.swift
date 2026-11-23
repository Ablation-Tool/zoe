import AVFoundation
import SwiftUI
import UIKit
import WebKit

/// Custom offline URL scheme handler serving bundled Dorothy 3D Brain Observatory
/// assets under `zoe-brain://local/...` with HTTP byte-range (206 Partial Content) support
/// so WebGL2, MNI152 MRI canvases, and offline MP4 walkthrough videos play smoothly with
/// zero external network traffic.
final class DorothyBrainSchemeHandler: NSObject, WKURLSchemeHandler {
    private let rootDirectory: URL

    init(rootDirectory: URL) {
        self.rootDirectory = rootDirectory.standardizedFileURL
        super.init()
    }

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let url = urlSchemeTask.request.url else {
            urlSchemeTask.didFailWithError(NSError(domain: "DorothyBrain", code: 400))
            return
        }
        var relative = url.path
        while relative.hasPrefix("/") {
            relative.removeFirst()
        }
        if relative.isEmpty {
            relative = "index.html"
        }
        let candidate = rootDirectory.appendingPathComponent(relative).standardizedFileURL
        let rootPrefix = rootDirectory.path.hasSuffix("/") ? rootDirectory.path : rootDirectory.path + "/"
        guard candidate.path.hasPrefix(rootPrefix),
              let data = try? Data(contentsOf: candidate) else {
            let notFound = HTTPURLResponse(
                url: url,
                statusCode: 404,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "text/plain; charset=utf-8"]
            )!
            urlSchemeTask.didReceive(notFound)
            urlSchemeTask.didReceive(Data("Not found".utf8))
            urlSchemeTask.didFinish()
            return
        }

        let mime = Self.mimeType(for: candidate.pathExtension.lowercased())
        let total = data.count

        if let rangeHeader = urlSchemeTask.request.value(forHTTPHeaderField: "Range"),
           rangeHeader.lowercased().hasPrefix("bytes="),
           total > 0 {
            let spec = rangeHeader.dropFirst("bytes=".count).split(separator: ",").first.map(String.init) ?? ""
            let parts = spec.split(separator: "-", omittingEmptySubsequences: false)
            let start = parts.count > 0 && !parts[0].isEmpty ? (Int(parts[0]) ?? 0) : 0
            let end = parts.count > 1 && !parts[1].isEmpty ? min(total - 1, Int(parts[1]) ?? (total - 1)) : (total - 1)
            if start >= 0 && start < total && end >= start {
                let slice = data.subdata(in: start..<(end + 1))
                let headers: [String: String] = [
                    "Content-Type": mime,
                    "Content-Length": "\(slice.count)",
                    "Content-Range": "bytes \(start)-\(end)/\(total)",
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-cache",
                    "Cross-Origin-Resource-Policy": "same-origin"
                ]
                let response = HTTPURLResponse(
                    url: url,
                    statusCode: 206,
                    httpVersion: "HTTP/1.1",
                    headerFields: headers
                )!
                urlSchemeTask.didReceive(response)
                urlSchemeTask.didReceive(slice)
                urlSchemeTask.didFinish()
                return
            }
        }

        let headers: [String: String] = [
            "Content-Type": mime,
            "Content-Length": "\(total)",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            "Cross-Origin-Resource-Policy": "same-origin"
        ]
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: headers
        )!
        urlSchemeTask.didReceive(response)
        urlSchemeTask.didReceive(data)
        urlSchemeTask.didFinish()
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {
        // Synchronous local bundle reads finish immediately; nothing pending to cancel.
    }

    private static func mimeType(for ext: String) -> String {
        switch ext {
        case "html": return "text/html; charset=utf-8"
        case "js": return "application/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json", "webmanifest": return "application/json; charset=utf-8"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "webp": return "image/webp"
        case "gif": return "image/gif"
        case "mp4": return "video/mp4"
        case "webm": return "video/webm"
        default: return "application/octet-stream"
        }
    }
}

final class DorothyBrainWebViewController: UIViewController, WKNavigationDelegate, WKScriptMessageHandler {
    private var webView: WKWebView!
    private let synthesizer = AVSpeechSynthesizer()
    var initialTab: String = ""
    var focusQuery: String = ""

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 7 / 255, green: 11 / 255, blue: 18 / 255, alpha: 1)

        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(self, name: "zoeSpeak")

        if let rootDir = Self.locateAssetDirectory() {
            configuration.setURLSchemeHandler(DorothyBrainSchemeHandler(rootDirectory: rootDir), forURLScheme: "zoe-brain")
            webView = WKWebView(frame: view.bounds, configuration: configuration)
            configureWebView()
            if let entry = URL(string: "zoe-brain://local/index.html") {
                webView.load(URLRequest(url: entry))
            }
        } else {
            webView = WKWebView(frame: view.bounds, configuration: configuration)
            configureWebView()
            webView.loadHTMLString(
                "<html><body style='background:#070b12;color:#e6edf7;font-family:-apple-system;padding:24px;'><h3>Dorothy 3d brain</h3><p>offline brain observatory assets were not found in this bundle.</p></body></html>",
                baseURL: nil
            )
        }
    }

    deinit {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "zoeSpeak")
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "zoeSpeak", let text = message.body as? String, !text.isEmpty {
            synthesizer.stopSpeaking(at: .immediate)
            let utterance = AVSpeechUtterance(string: text)
            utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
            synthesizer.speak(utterance)
        }
    }

    private func configureWebView() {
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.navigationDelegate = self
        webView.isOpaque = true
        webView.backgroundColor = UIColor(red: 7 / 255, green: 11 / 255, blue: 18 / 255, alpha: 1)
        webView.scrollView.backgroundColor = webView.backgroundColor
        webView.scrollView.bounces = false
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.accessibilityLabel = "Interactive 3D Dorothy Human Brain Observatory"
        view.addSubview(webView)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        applyInitialNavigation()
    }

    func applyInitialNavigation() {
        if !focusQuery.isEmpty {
            let escaped = escapeJs(focusQuery)
            focusQuery = ""
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                self?.webView?.evaluateJavaScript(
                    "window.__DOROTHY_ZOE_QA && window.__DOROTHY_ZOE_QA.focusFromQuery('\(escaped)');",
                    completionHandler: nil
                )
            }
            return
        }
        if !initialTab.isEmpty {
            let escaped = escapeJs(initialTab)
            initialTab = ""
            webView?.evaluateJavaScript("window.switchTab && window.switchTab('\(escaped)');", completionHandler: nil)
        }
    }

    func openAskZoeTab() {
        webView?.evaluateJavaScript("window.switchTab && window.switchTab('askzoe');", completionHandler: nil)
    }

    func resetCameraView() {
        let js = """
        (function() {
          if (typeof window.closeLightbox === 'function') { window.closeLightbox(); }
          if (typeof window.switchTab === 'function') { window.switchTab('brain3d'); }
          if (window.__DOROTHY_API && window.__DOROTHY_API.setCameraPreset) {
            window.__DOROTHY_API.setCameraPreset('hero');
          }
          window.scrollTo({ top: 0, behavior: 'smooth' });
        })();
        """
        webView?.evaluateJavaScript(js, completionHandler: nil)
    }

    private func escapeJs(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "'", with: "\\'")
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
    }

    private static func locateAssetDirectory() -> URL? {
        if let dir = Bundle.main.url(forResource: "dorothy_brain_observatory", withExtension: nil) {
            return dir
        }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("dorothy_brain_observatory"),
           FileManager.default.fileExists(atPath: res.appendingPathComponent("index.html").path) {
            return res
        }
        return nil
    }

    // Strict offline sandbox: only bundled zoe-brain:// assets may load.
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.scheme?.lowercased() == "zoe-brain" {
            decisionHandler(.allow)
            return
        }
        decisionHandler(.cancel)
    }
}

private struct DorothyBrainWebView: UIViewControllerRepresentable {
    let initialTab: String
    let focusQuery: String
    @Binding var resetToken: Int
    @Binding var askZoeToken: Int

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIViewController(context: Context) -> DorothyBrainWebViewController {
        let controller = DorothyBrainWebViewController()
        controller.initialTab = initialTab
        controller.focusQuery = focusQuery
        context.coordinator.controller = controller
        context.coordinator.lastResetToken = resetToken
        context.coordinator.lastAskToken = askZoeToken
        return controller
    }

    func updateUIViewController(_ uiViewController: DorothyBrainWebViewController, context: Context) {
        if context.coordinator.lastResetToken != resetToken {
            context.coordinator.lastResetToken = resetToken
            uiViewController.resetCameraView()
        }
        if context.coordinator.lastAskToken != askZoeToken {
            context.coordinator.lastAskToken = askZoeToken
            uiViewController.openAskZoeTab()
        }
    }

    final class Coordinator {
        weak var controller: DorothyBrainWebViewController?
        var lastResetToken = 0
        var lastAskToken = 0
    }
}

/// Native iOS / iPadOS host for the 100% offline Dorothy 3D Brain Observatory.
struct DorothyBrainObservatoryView: View {
    var initialTab: String = ""
    var focusQuery: String = ""
    @State private var resetToken = 0
    @State private var askZoeToken = 0

    var body: some View {
        DorothyBrainWebView(
            initialTab: initialTab,
            focusQuery: focusQuery,
            resetToken: $resetToken,
            askZoeToken: $askZoeToken
        )
        .ignoresSafeArea(edges: .bottom)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    askZoeToken += 1
                } label: {
                    Label("Ask Zoe", systemImage: "sparkles")
                        .font(.system(size: 13, weight: .semibold))
                }
                .accessibilityLabel("Ask Zoe neuroscience questions")

                Button {
                    resetToken += 1
                } label: {
                    Image(systemName: "arrow.counterclockwise")
                        .font(.system(size: 15, weight: .semibold))
                }
                .accessibilityLabel("Reset 3D brain view")
            }
        }
    }
}
