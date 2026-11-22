import SwiftUI
import UIKit

struct DeviceView: View {
    @StateObject private var speaker = Speaker()
    @State private var report = "Refresh to inspect local device state."
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Local battery, thermal state, and speaker check. Everything stays on your device.")
                    .font(.body)
                    .foregroundStyle(GemPalette.muted)

                Text(report)
                    .font(.body)
                    .foregroundStyle(GemPalette.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
                    .gemCard(radius: 22)

                HStack(spacing: 10) {
                    Button("Refresh", action: refresh)
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button("Speaker check") {
                        speaker.speak("Zoe speaker check. Measurement, evidence, belief, and action remain distinct.")
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                }

                Button("Open Google Gemini") {
                    if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                }
                .buttonStyle(GemKeycapButtonStyle())

                HStack(spacing: 14) {
                    Image("NuclideBrain")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 72)
                        .accessibilityLabel("NuClide Research dual-brain emblem")
                    Text("NuClide Research = Zoe + Nick + Cat · USA\nPlay. Learn. Adapt. Create. Explore. Share.")
                        .font(.footnote)
                        .foregroundStyle(GemPalette.muted)
                }
                .padding(14)
                .gemCard(radius: 20)

                Text("Private sensor streams are not exposed by public iOS APIs. No unavailable measurement is invented.")
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)
            }
            .padding(18)
        }
        .gemScreen()
        .onAppear {
            UIDevice.current.isBatteryMonitoringEnabled = true
            refresh()
        }
        .onDisappear {
            UIDevice.current.isBatteryMonitoringEnabled = false
            speaker.stop()
        }
    }

    private func refresh() {
        let device = UIDevice.current
        let level = device.batteryLevel >= 0 ? String(format: "%.0f%%", device.batteryLevel * 100) : "unavailable"
        let state: String
        switch device.batteryState {
        case .charging: state = "charging"
        case .full: state = "full"
        case .unplugged: state = "unplugged"
        default: state = "unknown"
        }
        let thermal: String
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: thermal = "nominal"
        case .fair: thermal = "fair"
        case .serious: thermal = "serious"
        case .critical: thermal = "critical"
        @unknown default: thermal = "unknown"
        }
        report = "Device: \(device.model)\nSystem: \(device.systemName) \(device.systemVersion)\nBattery: \(level) · \(state)\nThermal state: \(thermal)\n\nCapability is not correctness or authorization. Public API observations remain on device."
    }
}
