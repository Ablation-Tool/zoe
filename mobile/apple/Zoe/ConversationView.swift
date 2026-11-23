import AVFoundation
import SwiftUI
import UIKit

/// Zoe Next-Gen Chat Interface for Apple (iPhone, iPad & iPhone Duo Fold · v0.4.0-beta):
///   - Real user bubbles + Zoe GEM-anchored reply cards with collapsible Glass-Box Kloster telemetry
///   - Top Brain Switcher (`Zoe Stem` offline · `Cloud AI` multi-provider BYOK for Gemini/Claude/ChatGPT/Grok)
///   - Persistent multi-thread private history, Approval-Gated Multi-Step Action Plans,
///     and zero-key 1-tap handoff to Claude, Grok, ChatGPT & Gemini.
struct ConversationView: View {
    enum BrainMode: String, CaseIterable {
        case auto = "⚡ Auto"
        case stem = "Zoe Stem"
        case cloud = "Cloud AI"
    }

    var initialPrompt: String = ""
    var onGoHome: () -> Void = {}
    var onOpenMapsSafety: () -> Void = {}
    var onOpenBrainFocus: (String) -> Void = { _ in }
    @State private var didDispatchInitialPrompt = false

    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @StateObject private var nativeVoice = ZoeNativeVoice()
    @State private var brain = ZoeBrainEngine(defaults: .standard)

    @State private var brainMode: BrainMode = .auto
    @State private var webSearchEnabled = false
    @State private var activeProvider: MultiAiClient.Provider = .claude
    @State private var threads: [MultiAiClient.ChatThread] = []
    @State private var currentThreadIndex = 0
    @State private var expandedGlassIds: Set<String> = []
    @State private var pendingPlan: [OsToolsBridge.ActionSuggestion] = []

    @State private var active = false
    @State private var useNativeVoice = false
    @State private var torchOn = false
    @State private var typedMessage = ""
    @State private var status = "⚡ Auto hybrid ready (offline-first · tap Web: off for live citations)."
    @State private var lastResponse = "Hi, I'm Zoe. What would you like to explore?"
    @State private var showBrainSheet = false
    @State private var showThreadsSheet = false
    @Environment(\.openURL) private var openURL

    private static let threadsStorageKey = "zoe_swift_chat_threads_v1"

    private var currentMessages: [MultiAiClient.ChatMessage] {
        guard threads.indices.contains(currentThreadIndex) else { return [] }
        return threads[currentThreadIndex].messages
    }

    var body: some View {
        VStack(spacing: 0) {
            // Top Live Brain Mode Switcher Strip
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    modeChip("⚡ Auto", selected: brainMode == .auto) {
                        brainMode = .auto
                        status = "⚡ Auto hybrid active (offline-first + optional Cloud & Web)."
                    }
                    modeChip(webSearchEnabled ? "Web: on" : "Web: off", selected: webSearchEnabled) {
                        webSearchEnabled.toggle()
                        status = webSearchEnabled
                            ? "Live Web Grounding ON (zero-key DuckDuckGo + Wikipedia citations)."
                            : "Live Web Grounding OFF (100% offline local mode)."
                    }
                    modeChip("Zoe Stem", selected: brainMode == .stem) {
                        brainMode = .stem
                        status = "Zoe Stem active (offline · Kloster A_0.08 + SHA-256 memory)."
                    }
                    modeChip(activeProvider.displayName.components(separatedBy: " ").last ?? "Cloud AI", selected: brainMode == .cloud) {
                        brainMode = .cloud
                        status = "Cloud AI selected (\(activeProvider.displayName)). Tap Brain to set optional key."
                    }
                    modeChip("⚙ Brain", selected: false) { showBrainSheet = true }
                    modeChip("Threads", selected: false) { showThreadsSheet = true }
                    modeChip("+ New", selected: false) { startNewThread() }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)
            }

            Text(status)
                .font(.caption.weight(.medium))
                .foregroundStyle(GemPalette.cobalt)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 18)
                .padding(.bottom, 4)

            // Living Chat-Bubble Feed
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        if currentMessages.isEmpty {
                            welcomeCanvas
                        } else {
                            ForEach(currentMessages) { msg in
                                messageBubble(msg)
                                    .id(msg.id)
                            }
                        }

                        if !pendingPlan.isEmpty {
                            approvalPlanCard
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                }
                .onChange(of: currentMessages.count) { _, _ in
                    if let lastId = currentMessages.last?.id {
                        withAnimation { proxy.scrollTo(lastId, anchor: .bottom) }
                    }
                }
            }

            // Bottom Thumb-Zone Composer Dock
            VStack(spacing: 8) {
                HStack(spacing: 6) {
                    Button {
                        stop()
                        onOpenMapsSafety()
                    } label: {
                        Image(systemName: "map")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundStyle(GemPalette.ink)
                            .frame(width: 42, height: 42)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Open Maps and Safety")

                    TextField("Ask Zoe anything…", text: $typedMessage)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 10)
                        .submitLabel(.send)
                        .onSubmit(sendTyped)

                    Button("Send", action: sendTyped)
                        .buttonStyle(GemPrimaryButtonStyle())
                        .fixedSize()
                }
                .padding(6)
                .gemCard(radius: 28)

                HStack(spacing: 8) {
                    Button(active ? "Restart talking" : "Start talking", action: start)
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button("Stop", action: stop)
                        .buttonStyle(GemKeycapButtonStyle())
                    Menu("Ask AI ↗") {
                        Button("Claude (Prefill)") { openClaude(lastUserPrompt) }
                        Button("Grok") { if let u = URL(string: OsToolsBridge.grokWebUrl()) { openURL(u) } }
                        Button("ChatGPT") { if let u = URL(string: OsToolsBridge.chatGptWebUrl()) { openURL(u) } }
                        Button("Gemini") { if let u = URL(string: OsToolsBridge.geminiWebUrl()) { openURL(u) } }
                    }
                    .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ochre))
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 6)
            .padding(.bottom, 12)
        }
        .gemScreen()
        .sheet(isPresented: $showBrainSheet) {
            BrainCouncilSheet(
                activeProvider: $activeProvider,
                useNativeVoice: $useNativeVoice,
                onSelectCloud: { brainMode = .cloud },
                onSingZoe: {
                    status = "Singing Zoe's native soprano theme (44.1 kHz DSP, offline)…"
                    nativeVoice.singZoe()
                }
            )
            .presentationDetents([.large])
        }
        .sheet(isPresented: $showThreadsSheet) {
            NavigationStack {
                List {
                    ForEach(Array(threads.enumerated()), id: \.element.id) { idx, t in
                        Button {
                            currentThreadIndex = idx
                            showThreadsSheet = false
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(t.title).font(.body.weight(.medium)).foregroundStyle(GemPalette.ink)
                                Text("\(t.messages.count) messages").font(.caption).foregroundStyle(GemPalette.muted)
                            }
                        }
                    }
                }
                .navigationTitle("Private Chats")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("+ New") {
                            startNewThread()
                            showThreadsSheet = false
                        }
                    }
                }
            }
        }
        .onAppear {
            loadThreads()
            speech.onTranscript = handle
            speaker.onFinish = {
                if self.active { self.speech.start() }
            }
            if !didDispatchInitialPrompt, !initialPrompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                didDispatchInitialPrompt = true
                let p = initialPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                    processUserPrompt(p, resumeVoice: false)
                }
            }
        }
        .onDisappear(perform: stop)
    }

    private var welcomeCanvas: some View {
        VStack(spacing: 12) {
            Button(action: { stop(); onGoHome() }) {
                Image("RubySprout")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 52, height: 52)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Return to Zoe home")

            Text("Ask Zoe anything")
                .font(.title2.weight(.semibold))
                .foregroundStyle(GemPalette.greetingGradient)
            Text("Offline Glass-Box Brain · Native Voice · Multi-AI Council")
                .font(.footnote)
                .foregroundStyle(GemPalette.muted)
                .multilineTextAlignment(.center)

            ForEach([
                "What does Broca's area (BA 44) do?",
                "Where is the hippocampus and what is its role?",
                "Explain Cranial Nerve X (Vagus)",
                "Explain Kloster's A_tau(p) equation simply"
            ], id: \.self) { starter in
                Button("✦ \(starter)") {
                    typedMessage = starter
                    sendTyped()
                }
                .buttonStyle(GemKeycapButtonStyle())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 18)
    }

    @ViewBuilder
    private func messageBubble(_ msg: MultiAiClient.ChatMessage) -> some View {
        if msg.role == "user" {
            HStack {
                Spacer(minLength: 42)
                Text(msg.text)
                    .font(.body)
                    .foregroundStyle(GemPalette.ink)
                    .textSelection(.enabled)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(RoundedRectangle(cornerRadius: 22, style: .continuous).fill(GemPalette.cobalt.opacity(0.20)))
            }
        } else {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image("RubySprout").resizable().scaledToFit().frame(width: 20, height: 20)
                    Text(msg.provider.isEmpty ? "ZOE" : msg.provider)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.cobalt)
                }
                Text(msg.text)
                    .font(.body)
                    .foregroundStyle(GemPalette.ink)
                    .textSelection(.enabled)
                if !msg.sources.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(msg.sources, id: \.self) { entry in
                                let parts = entry.split(separator: "|", maxSplits: 1).map(String.init)
                                if parts.count == 2, WebSearchClient.isSafeWebUrl(parts[1]), let linkUrl = URL(string: parts[1]) {
                                    Link("🔗 \(parts[0]) ↗", destination: linkUrl)
                                        .font(.caption.weight(.medium))
                                        .foregroundStyle(GemPalette.seafoam)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 6)
                                        .background(Capsule().fill(GemPalette.surfaceHigh))
                                }
                            }
                        }
                    }
                }
                if !msg.glassBox.isEmpty {
                    let isOpen = expandedGlassIds.contains(msg.id)
                    Button(isOpen ? "✦ Glass-Box Telemetry ▾" : "✦ Glass-Box Telemetry ▸") {
                        if isOpen { expandedGlassIds.remove(msg.id) } else { expandedGlassIds.insert(msg.id) }
                    }
                    .font(.caption.weight(.medium))
                    .foregroundStyle(GemPalette.ochre)
                    if isOpen {
                        Text("\(msg.glassBox)\nHonesty: sentience_claimed=false · clone_claimed=false")
                            .font(.caption)
                            .foregroundStyle(GemPalette.muted)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 12).fill(GemPalette.surfaceHigh))
                    }
                }
                HStack(spacing: 10) {
                    if let neuro = NeuroscienceKnowledge.lookup(msg.text) {
                        Button("View in Dorothy 3D Brain") {
                            stop()
                            onOpenBrainFocus(neuro.focusQuery)
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.ochre)
                    }
                    Button("Speak") { speakReply(msg.text, resumeListening: false) }
                        .font(.caption.weight(.medium))
                    Button("Copy") { UIPasteboard.general.string = msg.text; status = "Copied reply." }
                        .font(.caption.weight(.medium))
                    Button("Ask Claude ↗") { openClaude(lastUserPrompt) }
                        .font(.caption.weight(.medium))
                }
                .foregroundStyle(GemPalette.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .gemCard(radius: 22)
        }
    }

    private var approvalPlanCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("APPROVAL-GATED PHONE ACTION PLAN · TAP TO RUN")
                .font(.caption.weight(.semibold))
                .foregroundStyle(GemPalette.seafoam)
            ForEach(Array(pendingPlan.enumerated()), id: \.offset) { idx, act in
                if act.kind == .navigate || act.kind == .mapSearch {
                    HStack(spacing: 8) {
                        Button("Step \(idx + 1): Apple Maps") { runAction(act, preferGoogle: false) }
                            .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.cobalt))
                        Button("Google Maps") { runAction(act, preferGoogle: true) }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.emerald))
                    }
                } else {
                    Button("Step \(idx + 1): \(act.label)") { runAction(act, preferGoogle: false) }
                        .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.cobalt))
                }
            }
            Button("Dismiss") { pendingPlan.removeAll() }
                .buttonStyle(GemKeycapButtonStyle())
        }
        .padding(14)
        .gemCard(radius: 20)
    }

    private func modeChip(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(selected ? GemPalette.primaryButtonInk : GemPalette.ink)
                .padding(.horizontal, 14)
                .frame(minHeight: 38)
                .background(Capsule().fill(selected ? GemPalette.primaryButtonFill : GemPalette.surface))
        }
        .buttonStyle(.plain)
    }

    private var lastUserPrompt: String {
        currentMessages.last(where: { $0.role == "user" })?.text ?? ""
    }

    private func sendTyped() {
        let msg = typedMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !msg.isEmpty else { return }
        typedMessage = ""
        processUserPrompt(msg, resumeVoice: false)
    }

    private func processUserPrompt(_ msg: String, resumeVoice: Bool) {
        appendMessage(MultiAiClient.ChatMessage(role: "user", text: msg, provider: "YOU"))
        let plan = OsToolsBridge.parseActionPlan(msg)
        if !plan.isEmpty { pendingPlan = plan }

        let lower = msg.lowercased()
        let isIdentityQuery = lower.contains("who are you") || lower.contains("who built you")
            || lower.contains("who made you") || lower.contains("who created you")
            || lower.contains("who controls you") || lower.contains("who owns you")
            || lower.contains("who governs you") || lower.contains("who designed you")
            || lower.contains("who programmed you") || lower.contains("who trained you")
            || lower.contains("your creator") || lower.contains("are you zoe")
            || lower.contains("are you really zoe")
            || lower.contains("what is your name") || lower.contains("what's your name")
            || lower.contains("alibaba") || lower.contains("are you qwen")

        let key = UserDefaults.standard.string(forKey: "zoe_ai_key_\(activeProvider.rawValue)") ?? ""
        let canUseCloud = activeProvider == .localOpenAI || !key.isEmpty
        let shouldRouteCloud = (brainMode == .cloud || (brainMode == .auto && canUseCloud)) && !isIdentityQuery && plan.isEmpty
        if shouldRouteCloud && canUseCloud {
            askCloudAsync(provider: activeProvider, apiKey: key, prompt: msg, useWeb: webSearchEnabled, resumeVoice: resumeVoice)
            return
        }
        if webSearchEnabled && !isIdentityQuery && plan.isEmpty {
            askLiveWebAsync(prompt: msg, resumeVoice: resumeVoice)
            return
        }

        let res = brain.respond(msg)
        lastResponse = res.reply
        appendMessage(MultiAiClient.ChatMessage(
            role: "zoe",
            text: res.reply,
            provider: "ZOE STEM · OFFLINE",
            glassBox: "\(res.telemetryBadge) · \(res.citation)"
        ))
        status = "Zoe Stem replied offline (0 cloud tokens)."
        speakReply(res.reply, resumeListening: resumeVoice)
    }

    private func fetchLiveWeb(_ query: String) async -> WebSearchClient.SearchResult {
        let cleaned = WebSearchClient.cleanSearchQuery(query)
        guard !cleaned.isEmpty,
              let enc = cleaned.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            return WebSearchClient.SearchResult(query: cleaned, sources: [])
        }
        var combined: [WebSearchClient.Source] = []
        var seen = Set<String>()
        if let ddgUrl = URL(string: "https://api.duckduckgo.com/?q=\(enc)&format=json&no_html=1&skip_disambig=1"),
           let (data, _) = try? await URLSession.shared.data(from: ddgUrl) {
            for s in WebSearchClient.parseDuckDuckGoJson(data) where seen.insert(s.url.lowercased()).inserted {
                combined.append(s)
            }
        }
        if let wikiUrl = URL(string: "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=\(enc)&srlimit=3&utf8=1&format=json"),
           let (data, _) = try? await URLSession.shared.data(from: wikiUrl) {
            for s in WebSearchClient.parseWikipediaSearchJson(data) where combined.count < 4 && seen.insert(s.url.lowercased()).inserted {
                combined.append(s)
            }
        }
        return WebSearchClient.SearchResult(query: cleaned, sources: combined)
    }

    private func askLiveWebAsync(prompt: String, resumeVoice: Bool) {
        status = "Searching live public web sources (HTTPS)…"
        Task {
            let sr = await fetchLiveWeb(prompt)
            await MainActor.run {
                if sr.hasSources {
                    let answer = sr.formatFallbackAnswer()
                    lastResponse = answer
                    appendMessage(MultiAiClient.ChatMessage(
                        role: "zoe",
                        text: answer,
                        provider: "ZOE LIVE WEB",
                        glassBox: "DuckDuckGo + Wikipedia · \(sr.sources.count) verified HTTPS sources",
                        sources: sr.sourceBadges
                    ))
                    status = "Live Web grounded (\(sr.sources.count) sources)."
                    speakReply(answer, resumeListening: resumeVoice)
                } else {
                    let res = brain.respond(prompt)
                    lastResponse = res.reply
                    appendMessage(MultiAiClient.ChatMessage(role: "zoe", text: res.reply, provider: "ZOE STEM · OFFLINE", glassBox: res.telemetryBadge))
                    status = "No direct web summary — offline Zoe Stem replied."
                    speakReply(res.reply, resumeListening: resumeVoice)
                }
            }
        }
    }

    private func askCloudAsync(provider: MultiAiClient.Provider, apiKey: String, prompt: String, useWeb: Bool, resumeVoice: Bool) {
        status = useWeb ? "Searching live web + asking \(provider.displayName)…" : "Asking \(provider.displayName)…"
        let model = UserDefaults.standard.string(forKey: "zoe_ai_model_\(provider.rawValue)") ?? provider.defaultModel
        let historySnapshot = currentMessages
        Task {
            let webRes = useWeb ? await fetchLiveWeb(prompt) : nil
            let webCtx = (webRes?.hasSources == true) ? (webRes?.formatContextForPrompt(maxChars: 1200) ?? "") : ""
            let badges = webRes?.sourceBadges ?? []
            do {
                let text = try await performCloudRequest(
                    provider: provider,
                    apiKey: apiKey,
                    model: model,
                    history: historySnapshot,
                    prompt: prompt,
                    webContext: webCtx,
                    enableSearch: useWeb
                )
                await MainActor.run {
                    lastResponse = text
                    appendMessage(MultiAiClient.ChatMessage(
                        role: "zoe",
                        text: text,
                        provider: "\(provider.displayName.uppercased()) · \(model)\(useWeb ? " · WEB" : "")",
                        glassBox: "Provider: \(provider.displayName) · Multi-turn\(webRes?.hasSources == true ? " · Live Web (\(webRes!.sources.count) sources)" : "")",
                        sources: badges
                    ))
                    status = "\(provider.displayName) replied."
                    speakReply(text, resumeListening: resumeVoice)
                }
            } catch {
                await MainActor.run {
                    let res = brain.respond(prompt)
                    lastResponse = res.reply
                    appendMessage(MultiAiClient.ChatMessage(
                        role: "zoe",
                        text: res.reply,
                        provider: "ZOE STEM · OFFLINE FALLBACK",
                        glassBox: res.telemetryBadge
                    ))
                    status = "\(provider.displayName) unreachable — offline Zoe Stem fallback."
                    speakReply(res.reply, resumeListening: resumeVoice)
                }
            }
        }
    }

    private func performCloudRequest(
        provider: MultiAiClient.Provider,
        apiKey: String,
        model: String,
        history: [MultiAiClient.ChatMessage],
        prompt: String,
        webContext: String,
        enableSearch: Bool
    ) async throws -> String {
        let sysPrompt = webContext.isEmpty
            ? MultiAiClient.zoeSystemPrompt
            : MultiAiClient.zoeSystemPrompt + "\n\nLive verified public web search context:\n" + webContext
        if provider == .gemini {
            let urlStr = "https://generativelanguage.googleapis.com/v1beta/models/\(model):generateContent?key=\(apiKey)"
            var req = URLRequest(url: URL(string: urlStr)!)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try MultiAiClient.buildGeminiGenerateBody(
                systemPrompt: sysPrompt,
                history: history,
                userPrompt: prompt,
                enableGoogleSearch: enableSearch
            )
            let (data, _) = try await URLSession.shared.data(for: req)
            return try MultiAiClient.parseGeminiReply(data)
        }
        if provider == .claude {
            var req = URLRequest(url: URL(string: provider.endpoint)!)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.setValue(apiKey, forHTTPHeaderField: "x-api-key")
            req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            req.httpBody = try MultiAiClient.buildClaudeMessagesBody(model: model, systemPrompt: sysPrompt, history: history, userPrompt: prompt)
            let (data, _) = try await URLSession.shared.data(for: req)
            return try MultiAiClient.parseClaudeMessagesReply(data)
        }
        let endpoint = try MultiAiClient.validateEndpoint(provider.endpoint)
        var req = URLRequest(url: URL(string: endpoint)!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if !apiKey.isEmpty {
            req.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }
        req.httpBody = try MultiAiClient.buildOpenAiChatBody(model: model, systemPrompt: sysPrompt, history: history, userPrompt: prompt)
        let (data, _) = try await URLSession.shared.data(for: req)
        return try MultiAiClient.parseOpenAiChatReply(data)
    }

    private func openClaude(_ prompt: String) {
        if let app = URL(string: OsToolsBridge.claudeDeepLinkUrl(prompt)), UIApplication.shared.canOpenURL(app) {
            openURL(app)
        } else if let web = URL(string: OsToolsBridge.claudeWebUrl(prompt)) {
            openURL(web)
        }
    }

    private func runAction(_ act: OsToolsBridge.ActionSuggestion, preferGoogle: Bool) {
        switch act.kind {
        case .navigate:
            if preferGoogle {
                if let app = URL(string: OsToolsBridge.googleMapsAppNavigationUrl(destination: act.query)),
                   UIApplication.shared.canOpenURL(app) { openURL(app) }
                else if let web = URL(string: OsToolsBridge.googleMapsWebDirectionsUrl(destination: act.query)) { openURL(web) }
            } else if let apple = URL(string: OsToolsBridge.appleMapsNavigationUrl(destination: act.query)) {
                openURL(apple)
            }
        case .mapSearch:
            let str = preferGoogle ? OsToolsBridge.googleMapsSearchUrl(query: act.query) : OsToolsBridge.appleMapsSearchUrl(query: act.query)
            if let u = URL(string: str) { openURL(u) }
        case .openLocation, .openSafety:
            stop()
            onOpenMapsSafety()
        case .toggleTorch:
            if let dev = AVCaptureDevice.default(for: .video), dev.hasTorch {
                try? dev.lockForConfiguration()
                torchOn.toggle()
                dev.torchMode = torchOn ? .on : .off
                dev.unlockForConfiguration()
                status = torchOn ? "Flashlight on." : "Flashlight off."
            }
        case .setTimer, .setAlarm:
            status = "iOS does not let third-party apps start Clock timers/alarms silently; open Clock or ask Siri."
        case .none:
            break
        }
    }

    private func startNewThread() {
        pendingPlan.removeAll()
        let fresh = MultiAiClient.ChatThread()
        threads.insert(fresh, at: 0)
        currentThreadIndex = 0
        saveThreads()
    }

    private func appendMessage(_ msg: MultiAiClient.ChatMessage) {
        if threads.isEmpty { threads = [MultiAiClient.ChatThread()] }
        if msg.role == "user", threads[currentThreadIndex].messages.isEmpty {
            threads[currentThreadIndex].title = MultiAiClient.titleFromPrompt(msg.text)
        }
        threads[currentThreadIndex].messages.append(msg)
        saveThreads()
    }

    private func loadThreads() {
        if let data = UserDefaults.standard.data(forKey: Self.threadsStorageKey),
           let decoded = try? JSONDecoder().decode([MultiAiClient.ChatThread].self, from: data),
           !decoded.isEmpty {
            threads = decoded
        } else {
            threads = [MultiAiClient.ChatThread()]
        }
        currentThreadIndex = 0
    }

    private func saveThreads() {
        let trimmed = Array(threads.prefix(24))
        if let data = try? JSONEncoder().encode(trimmed) {
            UserDefaults.standard.set(data, forKey: Self.threadsStorageKey)
        }
    }

    private func start() {
        active = true
        status = "Zoe is speaking…"
        speakReply(lastResponse, resumeListening: true)
    }

    private func handle(_ heard: String) {
        guard active else { return }
        if ConversationResponse.isStop(heard) {
            active = false
            processUserPrompt(heard, resumeVoice: false)
            status = "Conversation stopped. The microphone is off."
        } else {
            processUserPrompt(heard, resumeVoice: true)
        }
    }

    private func speakReply(_ text: String, resumeListening: Bool) {
        if useNativeVoice {
            nativeVoice.speak(text) {
                if resumeListening && self.active { self.speech.start() }
            }
        } else {
            speaker.speak(text)
        }
    }

    private func stop() {
        active = false
        speech.stop()
        speaker.stop()
        nativeVoice.stop()
        status = "Conversation stopped. The microphone is off."
    }
}

struct BrainCouncilSheet: View {
    @Binding var activeProvider: MultiAiClient.Provider
    @Binding var useNativeVoice: Bool
    var onSelectCloud: () -> Void
    var onSingZoe: () -> Void
    @State private var apiKey = ""
    @State private var modelName = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Cloud AI Provider (Optional BYOK)") {
                    Picker("Provider", selection: $activeProvider) {
                        ForEach(MultiAiClient.Provider.allCases) { p in
                            Text(p.displayName).tag(p)
                        }
                    }
                    SecureField("API Key (stored privately on device)", text: $apiKey)
                    TextField("Model ID", text: $modelName)
                    Button("Save & Activate Provider") {
                        UserDefaults.standard.set(apiKey.trimmingCharacters(in: .whitespacesAndNewlines),
                                                  forKey: "zoe_ai_key_\(activeProvider.rawValue)")
                        UserDefaults.standard.set(modelName.trimmingCharacters(in: .whitespacesAndNewlines),
                                                  forKey: "zoe_ai_model_\(activeProvider.rawValue)")
                        onSelectCloud()
                        dismiss()
                    }
                }
                Section("Zoe Native Voice (Offline 44.1 kHz)") {
                    Toggle("Use Zoe Native Formant Synth", isOn: $useNativeVoice)
                    Button("Sing Zoe") { onSingZoe() }
                }
            }
            .navigationTitle("Zoe Brain & Council")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } }
            }
            .onAppear(perform: loadFields)
            .onChange(of: activeProvider) { _, _ in loadFields() }
        }
    }

    private func loadFields() {
        apiKey = UserDefaults.standard.string(forKey: "zoe_ai_key_\(activeProvider.rawValue)") ?? ""
        modelName = UserDefaults.standard.string(forKey: "zoe_ai_model_\(activeProvider.rawValue)") ?? activeProvider.defaultModel
    }
}
