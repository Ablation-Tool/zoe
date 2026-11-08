import SwiftUI

@MainActor
final class TrinityModel: ObservableObject {
    @Published var endpoint = "http://127.0.0.1:8767"
    @Published var pairCode = ""
    @Published var probabilities = "0.70, 0.20, 0.08, 0.02"
    @Published var tau = "0.05"
    @Published var status = "Trinity is off. Enter the laptop address and connect explicitly."
    @Published var mobileReport = "Strict floating-point measurement appears after connection."
    @Published var tinyReport = "Quantized Q0.15 witness appears after connection."
    @Published var laptopReport = "Revision, history, and optional long-term memory appear after connection."
    @Published var history = "No shared observations loaded."
    @Published private(set) var connected = false
    @Published private(set) var busy = false

    private var task: Task<Void, Never>?
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 4
        configuration.timeoutIntervalForResource = 5
        configuration.waitsForConnectivity = false
        configuration.httpMaximumConnectionsPerHost = 2
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.httpCredentialStorage = nil
        return URLSession(configuration: configuration)
    }()

    func connect() {
        if connected {
            stop()
            status = "Trinity disconnected. No further laptop requests will be made."
            return
        }
        do {
            _ = try baseURL()
            connected = true
            status = "Connecting to the laptop companion…"
            task = Task { [weak self] in await self?.poll() }
        } catch {
            status = "Connection rejected: \(error.localizedDescription)"
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        connected = false
        busy = false
    }

    func measure() {
        guard connected else {
            status = "Connect the laptop before measuring together. Nothing was sent."
            return
        }
        do {
            guard probabilities.utf8.count <= 4096, tau.utf8.count <= 64 else {
                throw TrinityError.invalid("Distribution or threshold input is too long")
            }
            let values = try AccessibleVolume.parse(probabilities)
            guard let threshold = Double(tau) else { throw TrinityError.invalid("Invalid threshold") }
            _ = try TrinityMeasurement(probabilities: values, tau: threshold)
            Task { await perform(path: "/api/measure", body: [
                "source": "apple", "probabilities": values, "tau": threshold,
            ], forceInputs: true, success: "Measured together across all three planes.")
            }
        } catch {
            status = "Experiment rejected: \(error.localizedDescription)"
        }
    }

    func reset() {
        guard connected else { return }
        Task { await perform(path: "/api/reset", body: ["source": "apple"], forceInputs: true,
                             success: "Fresh shared view started.") }
    }

    private func poll() async {
        var first = true
        while !Task.isCancelled {
            await perform(path: "/api/state", body: nil, forceInputs: first, success: "Shared field synchronized.")
            first = false
            do {
                try await Task.sleep(nanoseconds: 1_500_000_000)
            } catch {
                return
            }
        }
    }

    private func perform(path: String, body: [String: Any]?, forceInputs: Bool, success: String) async {
        guard connected, !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let state = try await request(path: path, body: body)
            render(state, forceInputs: forceInputs)
            status = "\(success) Revision \(state.revision)."
        } catch is CancellationError {
            return
        } catch {
            if connected {
                status = "Trinity could not synchronize: \(error.localizedDescription). Check the laptop and pairing; no data was sent elsewhere."
            }
        }
    }

    private func render(_ state: TrinityState, forceInputs: Bool) {
        if forceInputs {
            probabilities = state.active.probabilities.map(String.init).joined(separator: ", ")
            tau = String(state.active.tau)
        }
        let mobile = state.active.zoe
        mobileReport = "Zoe mobile\nA = \(mobile.accessible) of \(mobile.vocabularySize) · complement = \(mobile.complement)\nStrict p > \(state.active.tau) · equality excluded\nNormalized accessible volume \(mobile.normalized)"
        let tiny = state.active.tiny
        tinyReport = "Tiny Zoe\nA = \(tiny.accessible) of \(tiny.vocabularySize) · complement = \(tiny.complement)\nQ0.15 τ = \(tiny.tau) / 32768\n\(state.active.quantizationChanged ? "Quantization changed the representation or count" : "Quantized count agrees with mobile")\nAPDU request \(tiny.request)\nAPDU response \(tiny.response)"
        laptopReport = state.memoryEnabled
            ? "Laptop Zoe\nRevision \(state.revision) · \(state.events.count) retained live observations\nLong-term journal: \(state.memoryRecords) events, verified on load\nTamper evidence, not authentication"
            : "Laptop Zoe\nRevision \(state.revision) · \(state.events.count) retained live observations\nMemory only · stopping the server erases this session"
        history = state.events.reversed().map { event in
            "#\(event.ordinal) · \(event.source) · τ \(event.tau)\nMobile A \(event.zoeAccessible)/\(event.zoeSize) · Tiny A \(event.tinyAccessible)/\(event.tinySize)"
        }.joined(separator: "\n")
        if history.isEmpty { history = "No shared measurements yet. Make the first mark." }
    }

    private func request(path: String, body: [String: Any]?) async throws -> TrinityState {
        var request = URLRequest(url: try baseURL().appendingPathComponent(String(path.dropFirst())))
        request.timeoutInterval = 4
        request.setValue("1", forHTTPHeaderField: "X-Zoe-Protocol")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if !pairCode.isEmpty { request.setValue(pairCode, forHTTPHeaderField: "X-Zoe-Pair") }
        if let body {
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } else {
            request.httpMethod = "GET"
        }
        let (data, response) = try await session.data(for: request)
        guard data.count <= 1_048_576 else { throw TrinityError.invalid("Laptop response exceeds 1 MiB") }
        guard let http = response as? HTTPURLResponse else { throw TrinityError.invalid("Invalid laptop response") }
        guard http.statusCode == 200 else {
            if let error = try? JSONDecoder().decode(ServerError.self, from: data) {
                throw TrinityError.invalid(error.error)
            }
            throw TrinityError.invalid("Laptop returned HTTP \(http.statusCode)")
        }
        return try TrinityState(data: data)
    }

    private func baseURL() throws -> URL {
        let value = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let components = URLComponents(string: value),
              components.scheme == "http", let host = components.host,
              components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil,
              components.path.isEmpty || components.path == "/",
              components.port == nil || components.port == 8767 else {
            throw TrinityError.invalid("Use an explicit HTTP laptop URL on port 8767")
        }
        let loopback = host == "127.0.0.1" || host == "localhost"
        guard loopback || Self.privateIPv4(host) else {
            throw TrinityError.invalid("Use loopback or an explicit private IPv4 laptop address")
        }
        if !loopback && pairCode.utf8.count < 16 {
            throw TrinityError.invalid("Trusted-Wi-Fi mode requires a pairing code of at least 16 characters")
        }
        guard let url = URL(string: value.hasSuffix("/") ? String(value.dropLast()) : value) else {
            throw TrinityError.invalid("Invalid laptop URL")
        }
        return url
    }

    private static func privateIPv4(_ host: String) -> Bool {
        let parts = host.split(separator: ".").compactMap { Int($0) }
        guard parts.count == 4, parts.allSatisfy({ (0...255).contains($0) }) else { return false }
        return parts[0] == 10
            || (parts[0] == 192 && parts[1] == 168)
            || (parts[0] == 172 && (16...31).contains(parts[1]))
            || (parts[0] == 169 && parts[1] == 254)
    }

    private struct ServerError: Decodable { let error: String }
}

struct TrinityView: View {
    @StateObject private var model = TrinityModel()
    @State private var confirmReset = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE")
                    .font(.caption.monospaced())
                    .foregroundStyle(.pink)
                Text("Zoe Trinity")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.cyan)
                Text("Three planes. One shared field. Tiny checks the bytes, mobile holds the experiment, and laptop keeps the long view.")
                Text(model.status)
                    .foregroundStyle(.yellow)
                    .accessibilityLabel("Trinity status")
                GroupBox("Laptop connection") {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField("http://192.168.1.10:8767", text: $model.endpoint)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                        SecureField("Pair code for trusted Wi-Fi", text: $model.pairCode)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                        Text("Loopback is for simulator/local development. On iPhone, start the laptop with --lan PRIVATE_IP and ZOE_TRINITY_PAIR. Pairing is not encryption; use a trusted network. Codes are not persisted.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, 8)
                }
                GroupBox("The shared experiment") {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField("Probabilities", text: $model.probabilities, axis: .vertical)
                            .textFieldStyle(.roundedBorder)
                            .lineLimit(2...5)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                        TextField("Threshold τ", text: $model.tau)
                            .textFieldStyle(.roundedBorder)
                            .keyboardType(.decimalPad)
                    }
                    .padding(.top, 8)
                }
                HStack {
                    Button(model.connected ? "Disconnect" : "Connect laptop", action: model.connect)
                    Button("Measure together", action: model.measure)
                        .disabled(!model.connected || model.busy)
                }
                .buttonStyle(.borderedProminent)
                Button("Fresh shared view") { confirmReset = true }
                    .buttonStyle(.bordered)
                    .disabled(!model.connected || model.busy)
                plane("01 · Tiny Zoe / cell plane", text: model.tinyReport, color: .yellow)
                plane("02 · Zoe mobile / native plane", text: model.mobileReport, color: .cyan)
                plane("03 · Laptop Zoe / field plane", text: model.laptopReport, color: .pink)
                plane("Field notes", text: model.history, color: .green)
                Text("Observation ≠ evidence ≠ belief update ≠ action. Nicholas Michael Kloster alone created the original equation on March 6, 2026.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .background(Color(red: 8 / 255, green: 13 / 255, blue: 24 / 255))
        .onDisappear(perform: model.stop)
        .confirmationDialog("Start a fresh shared view?", isPresented: $confirmReset) {
            Button("Fresh view", role: .destructive, action: model.reset)
            Button("Keep exploring", role: .cancel) {}
        } message: {
            Text("The live history will clear. An enabled laptop journal preserves all earlier events.")
        }
    }

    private func plane(_ title: String, text: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline.monospaced()).foregroundStyle(color)
            Text(text).font(.callout.monospaced()).textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(color, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}
