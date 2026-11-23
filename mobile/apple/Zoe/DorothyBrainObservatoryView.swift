import SwiftUI
import UIKit
import WebKit

/// Custom offline URL scheme handler serving bundled Dorothy 3D Brain Observatory
/// assets under `zoe-brain://local/...` so WebGL2 and MNI152 MRI canvases run with
/// a clean same-origin context and zero external network traffic.
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
        let headers: [String: String] = [
            "Content-Type": Self.mimeType(for: candidate.pathExtension.lowercased()),
            "Content-Length": "\(data.count)",
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
        default: return "application/octet-stream"
        }
    }
}

final class DorothyBrainWebViewController: UIViewController, WKNavigationDelegate {
    private var webView: WKWebView!

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 7 / 255, green: 11 / 255, blue: 18 / 255, alpha: 1)

        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.allowsInlineMediaPlayback = true
        configuration.websiteDataStore = .nonPersistent()

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

    func resetCameraView() {
        let js = """
        (function() {
          if (typeof window.closeLightbox === 'function') { window.closeLightbox(); }
          var hero = document.querySelector('[data-preset="hero"]');
          if (hero) { hero.click(); }
          var resetSlice = document.querySelector('[data-slice="reset"]');
          if (resetSlice) { resetSlice.click(); }
          var tissue = document.querySelector('[data-mode="tissue"]');
          if (tissue) { tissue.click(); }
          window.scrollTo({ top: 0, behavior: 'smooth' });
        })();
        """
        webView?.evaluateJavaScript(js, completionHandler: nil)
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
    @Binding var resetToken: Int

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIViewController(context: Context) -> DorothyBrainWebViewController {
        let controller = DorothyBrainWebViewController()
        context.coordinator.controller = controller
        context.coordinator.lastResetToken = resetToken
        return controller
    }

    func updateUIViewController(_ uiViewController: DorothyBrainWebViewController, context: Context) {
        if context.coordinator.lastResetToken != resetToken {
            context.coordinator.lastResetToken = resetToken
            uiViewController.resetCameraView()
        }
    }

    final class Coordinator {
        weak var controller: DorothyBrainWebViewController?
        var lastResetToken = 0
    }
}

/// Native iOS / iPadOS host for the 100% offline Dorothy 3D Brain Observatory.
struct DorothyBrainObservatoryView: View {
    @State private var resetToken = 0

    var body: some View {
        DorothyBrainWebView(resetToken: $resetToken)
            .ignoresSafeArea(edges: .bottom)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
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
