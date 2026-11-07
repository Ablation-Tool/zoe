import SwiftUI
import UIKit

struct DeviceView: View {
    @StateObject private var speaker = Speaker()
    @State private var report = "Refresh to inspect local device state."
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Device field")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.cyan)
                Image("NuclideBrain")
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: 160)
                    .accessibilityLabel("NuClide Research dual-brain co-brand")
                Text("NuClide Research = Zoe + Nick + Cat · USA\nStable and unstable in balance. PLACES = Play. Learn. Adapt. Create. Explore. Share. Research = fun = discovery.")
                    .font(.footnote)
                    .foregroundStyle(.pink)
                Text("Local capability and battery observations. No Zoe-authored telemetry or image upload.")
                    .foregroundStyle(.secondary)
                Text(report)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                HStack {
                    Button("Refresh", action: refresh)
                    Button("Speaker check") {
                        speaker.speak("Zoe speaker check. Measurement, evidence, belief, and action remain distinct.")
                    }
                }
                .buttonStyle(.borderedProminent)
                Button("Open Gemini") {
                    if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                }
                Text("Battery temperature and private sensor streams are not exposed by public iOS APIs. No unavailable measurement is invented.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .background(Color(red: 8 / 255, green: 13 / 255, blue: 24 / 255))
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
