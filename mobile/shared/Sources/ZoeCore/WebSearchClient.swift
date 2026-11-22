import Foundation

/// Opt-in Live Web Grounding Client for Zoe (v0.5.0-beta — Swift / Apple + Linux ZoeCore).
///
/// Zero API keys required, zero trackers, HTTPS-only:
///   - DuckDuckGo Instant Answer API
///   - Wikipedia Open Search API
/// Strictly idle until the user toggles Web Grounding on inside Zoe Chat.
public enum WebSearchClient {
    public struct Source: Codable, Equatable, Identifiable, Sendable {
        public let id: String
        public let title: String
        public let snippet: String
        public let url: String
        public let domain: String

        public init(title: String, snippet: String, url: String, domain: String) {
            self.id = url
            self.title = title.trimmingCharacters(in: .whitespacesAndNewlines)
            self.snippet = snippet.trimmingCharacters(in: .whitespacesAndNewlines)
            self.url = url.trimmingCharacters(in: .whitespacesAndNewlines)
            self.domain = domain.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        public var badgeEntry: String {
            let raw = domain.isEmpty ? title : "\(domain) · \(title)"
            let label = raw.count > 44 ? String(raw.prefix(43)) + "…" : raw
            return "\(label)|\(url)"
        }
    }

    public struct SearchResult: Equatable, Sendable {
        public let query: String
        public let sources: [Source]

        public init(query: String, sources: [Source]) {
            self.query = query
            self.sources = sources
        }

        public var hasSources: Bool { !sources.isEmpty }

        public var sourceBadges: [String] {
            sources.filter { WebSearchClient.isSafeWebUrl($0.url) }.map(\.badgeEntry)
        }

        public func formatContextForPrompt(maxChars: Int = 900) -> String {
            var out = ""
            for (idx, s) in sources.enumerated() {
                let entry = "[\(idx + 1)] \(s.title) (\(s.domain)): \(s.snippet)\n"
                if out.count + entry.count > maxChars { break }
                out += entry
            }
            return out.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        public func formatFallbackAnswer() -> String {
            guard !sources.isEmpty else {
                return "Live Web search found no direct public encyclopedia summary for \"\(query)\"."
            }
            var lines = ["Here is what live public web sources report for \"\(query)\":"]
            for (idx, s) in sources.enumerated() {
                lines.append("\(idx + 1). \(s.title) — \(s.snippet)")
            }
            lines.append("Tap any source chip below to open the original page directly.")
            return lines.joined(separator: "\n\n")
        }
    }

    public static func isSafeWebUrl(_ url: String) -> Bool {
        url.trimmingCharacters(in: .whitespacesAndNewlines).lowercased().hasPrefix("https://")
    }

    public static func cleanSearchQuery(_ raw: String) -> String {
        var q = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
        let prefixes = [
            "search the web for ", "search web for ", "web search for ", "search for ",
            "look up ", "find info on ", "what is the latest on ", "tell me about ",
            "explain ", "who is ", "what is ", "what are ", "where is ", "when was ",
        ]
        let lower = q.lowercased()
        for p in prefixes {
            if lower.hasPrefix(p), q.count > p.count + 1 {
                q = String(q.dropFirst(p.count)).trimmingCharacters(in: .whitespacesAndNewlines)
                break
            }
        }
        while let last = q.last, "?!.".contains(last) {
            q.removeLast()
        }
        q = q.trimmingCharacters(in: .whitespacesAndNewlines)
        return q.count > 120 ? String(q.prefix(120)).trimmingCharacters(in: .whitespacesAndNewlines) : q
    }

    public static func stripHtml(_ raw: String) -> String {
        var out = ""
        var inTag = false
        for ch in raw {
            if ch == "<" {
                inTag = true
                out.append(" ")
            } else if ch == ">" {
                inTag = false
            } else if !inTag {
                out.append(ch)
            }
        }
        return out
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&#039;", with: "'")
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
    }

    public static func extractDomain(_ url: String) -> String {
        guard isSafeWebUrl(url), let host = URL(string: url)?.host else { return "web" }
        let cleaned = host.hasPrefix("www.") ? String(host.dropFirst(4)) : host
        return cleaned.hasPrefix("en.wikipedia.org") ? "Wikipedia" : cleaned
    }

    public static func parseDuckDuckGoJson(_ data: Data) -> [Source] {
        guard let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        var out: [Source] = []
        let heading = (root["Heading"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let abstract = stripHtml(root["AbstractText"] as? String ?? "")
        let url = (root["AbstractURL"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if !abstract.isEmpty && isSafeWebUrl(url) {
            out.append(Source(
                title: heading.isEmpty ? "Instant Summary" : heading,
                snippet: trimSnippet(abstract, max: 240),
                url: url,
                domain: extractDomain(url)
            ))
        }
        if let topics = root["RelatedTopics"] as? [[String: Any]] {
            for item in topics where out.count < 2 {
                let text = stripHtml(item["Text"] as? String ?? "")
                let firstUrl = (item["FirstURL"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                if !text.isEmpty && isSafeWebUrl(firstUrl) {
                    let title = text.components(separatedBy: " - ").first ?? trimSnippet(text, max: 44)
                    out.append(Source(title: title, snippet: trimSnippet(text, max: 200), url: firstUrl, domain: extractDomain(firstUrl)))
                }
            }
        }
        return out
    }

    public static func parseWikipediaSearchJson(_ data: Data) -> [Source] {
        guard let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let query = root["query"] as? [String: Any],
              let hits = query["search"] as? [[String: Any]] else { return [] }
        var out: [Source] = []
        for item in hits where out.count < 3 {
            let title = (item["title"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            let snippet = stripHtml(item["snippet"] as? String ?? "")
            guard !title.isEmpty && !snippet.isEmpty else { continue }
            let slug = title.replacingOccurrences(of: " ", with: "_")
                .addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? title
            let url = "https://en.wikipedia.org/wiki/\(slug)"
            out.append(Source(title: title, snippet: trimSnippet(snippet, max: 220), url: url, domain: "Wikipedia"))
        }
        return out
    }

    private static func trimSnippet(_ s: String, max: Int) -> String {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.count > max ? String(t.prefix(max - 1)).trimmingCharacters(in: .whitespacesAndNewlines) + "…" : t
    }
}
