import AVFoundation
import SwiftUI
import WebKit

final class SafeConvertViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    private var webView: WKWebView!
    private var privacyShield: UIVisualEffectView?
    private let speechSynth = AVSpeechSynthesizer()

    override func viewDidLoad() {
        super.viewDidLoad()
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.allowsInlineMediaPlayback = true
        configuration.websiteDataStore = .default()
        configuration.userContentController.add(self, name: "zoeSafeSpeech")
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
        guard let baseUrl = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "safeconvert") else {
            webView.loadHTMLString("<p>SafeConvert resource is missing.</p>", baseURL: nil)
            return
        }
        let region = Self.detectRegionCode()
        let lang = Self.detectLangCode()
        let theme = traitCollection.userInterfaceStyle == .dark ? "dark" : "light"
        var components = URLComponents(url: baseUrl, resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "theme", value: theme),
            URLQueryItem(name: "region", value: region),
            URLQueryItem(name: "lang", value: lang),
        ]
        let loadUrl = components?.url ?? baseUrl
        webView.loadFileURL(loadUrl, allowingReadAccessTo: baseUrl.deletingLastPathComponent())
    }

    static func detectRegionCode() -> String {
        let code = (Locale.current.region?.identifier ?? "US").uppercased()
        if ["US", "PR", "VI", "GU"].contains(code) { return "US" }
        if ["GB", "UK"].contains(code) { return "UK" }
        if code == "CA" { return "CA" }
        if ["AU", "NZ"].contains(code) { return "AU" }
        if code == "IN" { return "IN" }
        let eu: Set<String> = [
            "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
            "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
            "SI", "ES", "SE", "NO", "IS", "LI", "CH"
        ]
        if eu.contains(code) { return "EU" }
        let latam: Set<String> = [
            "MX", "AR", "CO", "CL", "PE", "BR", "UY", "EC", "GT", "CR", "PA",
            "DO", "HN", "SV", "NI", "BO", "PY", "VE"
        ]
        if latam.contains(code) { return "MX" }
        return "GLOBAL"
    }

    static func detectLangCode() -> String {
        let lang = (Locale.current.language.languageCode?.identifier ?? "en").lowercased()
        if ["en", "es", "fr", "de", "pt"].contains(lang) { return lang }
        return "en"
    }

    // MARK: Calm story voice bridge (instant kill on background or EXIT)

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "zoeSafeSpeech", let body = message.body as? [String: String] else { return }
        if body["action"] == "stop" {
            speechSynth.stopSpeaking(at: .immediate)
            return
        }
        if body["action"] == "speak", let text = body["text"], !text.isEmpty {
            speechSynth.stopSpeaking(at: .immediate)
            let utterance = AVSpeechUtterance(string: String(text.prefix(2800)))
            utterance.rate = 0.44
            utterance.voice = AVSpeechSynthesisVoice(language: body["lang"] ?? "en-US")
            speechSynth.speak(utterance)
        }
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
        speechSynth.stopSpeaking(at: .immediate)
        webView?.evaluateJavaScript("if (typeof exitHelp === 'function') { exitHelp(); }", completionHandler: nil)
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
        speechSynth.stopSpeaking(at: .immediate)
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
        let scheme = url.scheme?.lowercased() ?? ""
        if navigationAction.navigationType == .linkActivated {
            if scheme == "geo" {
                let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                    .queryItems?.first(where: { $0.name == "q" })?.value ?? "hospital"
                if let appleMaps = URL(string: "https://maps.apple.com/?q=" + (query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "hospital")) {
                    UIApplication.shared.open(appleMaps)
                }
            } else if ["tel", "sms", "mailto", "https", "maps"].contains(scheme) {
                UIApplication.shared.open(url)
            }
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
