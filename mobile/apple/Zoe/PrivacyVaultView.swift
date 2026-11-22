import CryptoKit
import SwiftUI

/// Zoe Signal-Grade Privacy & E2EE Vault for Apple (iOS 17+ · v0.6.0-beta).
struct PrivacyVaultView: View {
    @State private var privateKey = P256.KeyAgreement.PrivateKey()
    @State private var noteText = ""
    @State private var outputText = "Locked or unlocked note appears here."
    @State private var statusText = "🔒 On-device AES-256 encryption active."

    private var safetyNumber: String {
        let raw = Array(privateKey.publicKey.rawRepresentation)
        return ZoeSignalAndWakeCore.computeSafetyNumber(keyA: raw, keyB: raw)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(statusText)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(GemPalette.emerald)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .gemCard(radius: 18)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Safety Number")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(GemPalette.ink)
                    Text(safetyNumber)
                        .font(.body.monospaced())
                        .foregroundStyle(GemPalette.ink)
                        .textSelection(.enabled)
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .gemCard(radius: 22)

                VStack(alignment: .leading, spacing: 10) {
                    Text("Encrypt a Note")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(GemPalette.ink)
                    Text("ECDH + AES-256-GCM · stays on your device")
                        .font(.caption)
                        .foregroundStyle(GemPalette.muted)
                    TextField("Write a note to lock…", text: $noteText)
                        .textFieldStyle(.plain)
                        .padding(12)
                        .background(RoundedRectangle(cornerRadius: 14).fill(GemPalette.surfaceHigh))
                    HStack(spacing: 8) {
                        Button("🔒 Lock Note") { sealSelf() }
                            .buttonStyle(GemPrimaryButtonStyle())
                        Button("🔓 Unlock") { unsealSelf() }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.emerald))
                    }
                    Text(outputText)
                        .font(.caption.monospaced())
                        .foregroundStyle(GemPalette.ink)
                        .textSelection(.enabled)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 14).fill(GemPalette.surfaceHigh))
                }
                .padding(16)
                .gemCard(radius: 22)
            }
            .padding(16)
        }
        .gemScreen()
    }

    private func deriveKey(ephemeralPub: P256.KeyAgreement.PublicKey) throws -> SymmetricKey {
        let shared = try privateKey.sharedSecretFromKeyAgreement(with: ephemeralPub)
        return shared.hkdfDerivedSymmetricKey(
            using: SHA256.self,
            salt: ephemeralPub.rawRepresentation,
            sharedInfo: Data("ZoeSignalE2EE-v1".utf8),
            outputByteCount: 32
        )
    }

    private func sealSelf() {
        let clean = noteText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }
        do {
            let eph = P256.KeyAgreement.PrivateKey()
            let shared = try eph.sharedSecretFromKeyAgreement(with: privateKey.publicKey)
            let key = shared.hkdfDerivedSymmetricKey(
                using: SHA256.self,
                salt: eph.publicKey.rawRepresentation,
                sharedInfo: Data("ZoeSignalE2EE-v1".utf8),
                outputByteCount: 32
            )
            let sealed = try AES.GCM.seal(Data(clean.utf8), using: key)
            guard let combined = sealed.combined else { return }
            outputText = "ZOE-SIGNAL-V1:\(eph.publicKey.rawRepresentation.base64EncodedString()).\(combined.base64EncodedString())"
            statusText = "Sealed with ephemeral P-256 ECDH + HKDF-SHA256 + AES-256-GCM."
        } catch {
            statusText = "Seal error: \(error.localizedDescription)"
        }
    }

    private func unsealSelf() {
        let raw = outputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.hasPrefix("ZOE-SIGNAL-V1:") else { return }
        let parts = raw.dropFirst("ZOE-SIGNAL-V1:".count).split(separator: ".", maxSplits: 1)
        guard parts.count == 2,
              let ephData = Data(base64Encoded: String(parts[0])),
              let ctData = Data(base64Encoded: String(parts[1])) else { return }
        do {
            let ephPub = try P256.KeyAgreement.PublicKey(rawRepresentation: ephData)
            let key = try deriveKey(ephemeralPub: ephPub)
            let box = try AES.GCM.SealedBox(combined: ctData)
            let plain = try AES.GCM.open(box, using: key)
            outputText = String(decoding: plain, as: UTF8.self)
            statusText = "Verified AES-256-GCM tag and decrypted cleanly on-device!"
        } catch {
            statusText = "Unseal error: \(error.localizedDescription)"
        }
    }
}
