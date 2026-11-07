import SwiftUI
import WebKit

final class SafeConvertViewController: UIViewController, WKNavigationDelegate {
    private var webView: WKWebView!

    override func viewDidLoad() {
        super.viewDidLoad()
        let configuration = WKWebViewConfiguration()
        configuration.preferences.javaScriptEnabled = true
        configuration.websiteDataStore = .default()
        webView = WKWebView(frame: view.bounds, configuration: configuration)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.navigationDelegate = self
        webView.accessibilityLabel = "Offline unit converter and safety resources"
        view.addSubview(webView)
        guard let url = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "safeconvert") else {
            webView.loadHTMLString("<p>SafeConvert resource is missing.</p>", baseURL: nil)
            return
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
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
