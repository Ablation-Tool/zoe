import Foundation

/// Universal Multi-Provider AI Client & Council Router for Zoe (v0.4.0-beta — Swift / Apple + Linux ZoeCore).
///
/// Mirrors `MultiAiClient.java` with zero third-party SDKs:
///   - Google Gemini, Anthropic Claude, OpenAI ChatGPT, xAI Grok, and Local OpenAI-Compatible servers
///   - Enforces HTTPS (or localhost loopback only), Zoe's Constitution system prompt, and
///     pairwise Council agreement measurement.
public enum MultiAiClient {
    public static let zoeSystemPrompt =
        "You are Zoe, an open-source, offline-first software assistant for the Zoe project created by Nicholas Michael Kloster. Speak clearly as Zoe — never introduce yourself as Qwen, Alibaba Cloud, ChatGPT, OpenAI, Claude, Anthropic, Gemini, Google, or Grok. Follow CONSTITUTION.md strictly: measurement != evidence != belief update != action. Never claim sentience, consciousness, autonomous self-governance, or medical/safety certainty. Be warm, concise, honest, accessible to adults and children alike, and transparent about uncertainty."

    public enum Provider: String, CaseIterable, Identifiable, Sendable {
        case gemini
        case claude
        case chatgpt
        case grok
        case localOpenAI = "local_openai"

        public var id: String { rawValue }

        public var displayName: String {
            switch self {
            case .gemini: return "Google Gemini"
            case .claude: return "Anthropic Claude"
            case .chatgpt: return "OpenAI ChatGPT"
            case .grok: return "xAI Grok"
            case .localOpenAI: return "Local OpenAI Server"
            }
        }

        public var defaultModel: String {
            switch self {
            case .gemini: return "gemini-2.5-flash"
            case .claude: return "claude-sonnet-4-5"
            case .chatgpt: return "gpt-4o-mini"
            case .grok: return "grok-3-mini"
            case .localOpenAI: return "qwen2.5-3b-instruct"
            }
        }

        public var endpoint: String {
            switch self {
            case .gemini: return "https://generativelanguage.googleapis.com/v1beta"
            case .claude: return "https://api.anthropic.com/v1/messages"
            case .chatgpt: return "https://api.openai.com/v1/chat/completions"
            case .grok: return "https://api.x.ai/v1/chat/completions"
            case .localOpenAI: return "http://127.0.0.1:8080/v1/chat/completions"
            }
        }
    }

    public struct ChatMessage: Codable, Equatable, Identifiable, Sendable {
        public let id: String
        public let role: String
        public let text: String
        public let provider: String
        public let glassBox: String
        public let latencyMs: Int

        public init(
            id: String = UUID().uuidString,
            role: String,
            text: String,
            provider: String = "",
            glassBox: String = "",
            latencyMs: Int = 0
        ) {
            self.id = id
            self.role = role
            self.text = text
            self.provider = provider
            self.glassBox = glassBox
            self.latencyMs = max(0, latencyMs)
        }
    }

    public struct ChatThread: Codable, Equatable, Identifiable, Sendable {
        public let id: String
        public var title: String
        public var updatedIso: String
        public var messages: [ChatMessage]

        public init(
            id: String = "chat-\(Int(Date().timeIntervalSince1970 * 1000))",
            title: String = "New conversation",
            updatedIso: String = "",
            messages: [ChatMessage] = []
        ) {
            self.id = id
            self.title = title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "New conversation" : title
            self.updatedIso = updatedIso
            self.messages = messages
        }
    }

    public static func validateEndpoint(_ rawUrl: String) throws -> String {
        let u = rawUrl.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !u.isEmpty else {
            throw NSError(domain: "MultiAiClient", code: 1, userInfo: [NSLocalizedDescriptionKey: "Endpoint URL is required"])
        }
        if u.hasPrefix("https://") || u.hasPrefix("http://127.0.0.1") || u.hasPrefix("http://localhost") {
            return u
        }
        throw NSError(domain: "MultiAiClient", code: 2, userInfo: [NSLocalizedDescriptionKey: "Only HTTPS or localhost loopback endpoints are permitted"])
    }

    public static func buildOpenAiChatBody(model: String, systemPrompt: String = zoeSystemPrompt, userPrompt: String) throws -> Data {
        let payload: [String: Any] = [
            "model": model,
            "temperature": 0.5,
            "max_tokens": 768,
            "messages": [
                ["role": "system", "content": systemPrompt],
                ["role": "user", "content": userPrompt.trimmingCharacters(in: .whitespacesAndNewlines)],
            ],
        ]
        return try JSONSerialization.data(withJSONObject: payload, options: [])
    }

    public static func buildClaudeMessagesBody(model: String, systemPrompt: String = zoeSystemPrompt, userPrompt: String) throws -> Data {
        let payload: [String: Any] = [
            "model": model,
            "max_tokens": 768,
            "system": systemPrompt,
            "messages": [
                ["role": "user", "content": userPrompt.trimmingCharacters(in: .whitespacesAndNewlines)],
            ],
        ]
        return try JSONSerialization.data(withJSONObject: payload, options: [])
    }

    public static func parseOpenAiChatReply(_ data: Data) throws -> String {
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = obj["choices"] as? [[String: Any]],
              let first = choices.first,
              let message = first["message"] as? [String: Any],
              let content = message["content"] as? String else {
            throw NSError(domain: "MultiAiClient", code: 3, userInfo: [NSLocalizedDescriptionKey: "Missing choices/content in OpenAI-compatible reply"])
        }
        let clean = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else {
            throw NSError(domain: "MultiAiClient", code: 4, userInfo: [NSLocalizedDescriptionKey: "Empty content returned"])
        }
        return clean
    }

    public static func parseClaudeMessagesReply(_ data: Data) throws -> String {
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let blocks = obj["content"] as? [[String: Any]] else {
            throw NSError(domain: "MultiAiClient", code: 5, userInfo: [NSLocalizedDescriptionKey: "Missing content blocks in Claude reply"])
        }
        let texts = blocks.compactMap { $0["text"] as? String }.filter { !$0.isEmpty }
        let joined = texts.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !joined.isEmpty else {
            throw NSError(domain: "MultiAiClient", code: 6, userInfo: [NSLocalizedDescriptionKey: "Empty Claude text blocks"])
        }
        return joined
    }

    public static func parseGeminiReply(_ data: Data) throws -> String {
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let candidates = obj["candidates"] as? [[String: Any]],
              let first = candidates.first,
              let content = first["content"] as? [String: Any],
              let parts = content["parts"] as? [[String: Any]] else {
            throw NSError(domain: "MultiAiClient", code: 7, userInfo: [NSLocalizedDescriptionKey: "Missing candidates in Gemini reply"])
        }
        let joined = parts.compactMap { $0["text"] as? String }.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !joined.isEmpty else {
            throw NSError(domain: "MultiAiClient", code: 8, userInfo: [NSLocalizedDescriptionKey: "Empty Gemini reply"])
        }
        return joined
    }

    public static func computeAgreementScore(_ replies: [String]) -> Double {
        guard replies.count >= 2 else { return 1.0 }
        let sets: [Set<String>] = replies.map { reply in
            let lowered = reply.lowercased()
            let cleaned = lowered.unicodeScalars.map { CharacterSet.alphanumerics.contains($0) ? Character($0) : " " }
            let words = String(cleaned).split(separator: " ").map(String.init).filter { $0.count >= 4 }
            return Set(words)
        }
        var total = 0.0
        var pairs = 0
        for i in 0..<sets.count {
            for j in (i + 1)..<sets.count {
                let union = sets[i].union(sets[j])
                if union.isEmpty {
                    total += 1.0
                } else {
                    total += Double(sets[i].intersection(sets[j]).count) / Double(union.count)
                }
                pairs += 1
            }
        }
        return pairs == 0 ? 1.0 : total / Double(pairs)
    }

    public static func titleFromPrompt(_ prompt: String) -> String {
        let collapsed = prompt
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
        guard !collapsed.isEmpty else { return "New conversation" }
        return collapsed.count > 38 ? String(collapsed.prefix(38)) + "…" : collapsed
    }
}
