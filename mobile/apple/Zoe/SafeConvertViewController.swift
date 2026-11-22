import SwiftUI
import WebKit

final class SafeConvertViewController: UIViewController, WKNavigationDelegate, WKUIDelegate {
    private var webView: WKWebView!
    private var privacyShield: UIVisualEffectView?

    override func viewDidLoad() {
        super.viewDidLoad()
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.allowsInlineMediaPlayback = true
        configuration.websiteDataStore = .default()
        webView = WKWebView(frame: view.bounds, configuration: configuration)
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.accessibilityLabel = "Offline unit converter and safety resources"
        view.addSubview(webView)
        installPrivacyShield()
        guard let url = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "safeconvert") else {
            webView.loadHTMLString("<p>SafeConvert resource is missing.</p>", baseURL: nil)
            return
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }

    // MARK: App-switcher privacy shield (mirrors Android FLAG_SECURE)

    private func installPrivacyShield() {
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(coverForBackground),
                           name: UIApplication.willResignActiveNotification, object: nil)
        center.addObserver(self, selector: #selector(uncoverForForeground),
                           name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    @objc private func coverForBackground() {
        guard privacyShield == nil else { return }
        let shield = UIVisualEffectView(effect: UIBlurEffect(style: .systemThickMaterial))
        shield.frame = view.bounds
        shield.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        shield.isAccessibilityElement = false
        view.addSubview(shield)
        privacyShield = shield
    }

    @objc private func uncoverForForeground() {
        privacyShield?.removeFromSuperview()
        privacyShield = nil
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    // MARK: Media capture (audio/video evidence) only for the bundled local page

    @available(iOS 15.0, *)
    func webView(_ webView: WKWebView,
                 requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo,
                 type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(origin.protocol == "file" ? .prompt : .deny)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.isFileURL {
            decisionHandler(.allow)
            return
        }
        if navigationAction.navigationType == .linkActivated,
           ["tel", "sms", "mailto", "https"].contains(url.scheme?.lowercased() ?? "") {
            UIApplication.shared.open(url)
        }
        decisionHandler(.cancel)
    }
}

struct SafeConvertView: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> SafeConvertViewController {
        SafeConvertViewController()
    }

    func updateUIViewController(_ controller: SafeConvertViewController, context: Context) {
    }
}
