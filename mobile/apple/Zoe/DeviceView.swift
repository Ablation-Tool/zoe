import SwiftUI
import UIKit

struct DeviceView: View {
    @StateObject private var speaker = Speaker()
    @State private var modelName = UIDevice.current.model
    @State private var osLabel = "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)"
    @State private var batteryLabel = "Checking…"
    @State private var thermalLabel = "Nominal"
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Battery, thermal state & speaker check.")
                    .font(.subheadline)
                    .foregroundStyle(GemPalette.muted)
                    .padding(.horizontal, 4)

                VStack(spacing: 0) {
                    settingRow("Model", value: modelName)
                    Divider().overlay(GemPalette.hairline).padding(.horizontal, 16)
                    settingRow("System", value: osLabel)
                    Divider().overlay(GemPalette.hairline).padding(.horizontal, 16)
                    settingRow("Battery", value: batteryLabel)
                    Divider().overlay(GemPalette.hairline).padding(.horizontal, 16)
                    settingRow("Thermal", value: thermalLabel)
                }
                .padding(.vertical, 4)
                .gemCard(radius: 22)

                HStack(spacing: 10) {
                    Button("Refresh", action: refresh)
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button("Speaker check") {
                        speaker.speak("Zoe speaker check. Audio is working clearly.")
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                }

                Button("Open Gemini") {
                    if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                }
                .buttonStyle(GemKeycapButtonStyle())

                Text("Checked locally on your device. Capability is not proof or permission.")
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 4)
            }
            .padding(16)
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

    private func settingRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.body)
                .foregroundStyle(GemPalette.ink)
            Spacer()
            Text(value)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(GemPalette.muted)
        }
        .padding(.horizontal, 16)
        .frame(minHeight: 46)
    }

    private func refresh() {
        let device = UIDevice.current
        modelName = device.model
        osLabel = "\(device.systemName) \(device.systemVersion)"
        let level = device.batteryLevel >= 0 ? String(format: "%.0f%%", device.batteryLevel * 100) : "Unavailable"
        let state: String
        switch device.batteryState {
        case .charging: state = "Charging"
        case .full: state = "Full"
        case .unplugged: state = "Battery"
        default: state = "Unknown"
        }
        batteryLabel = "\(level) · \(state)"
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: thermalLabel = "Nominal"
        case .fair: thermalLabel = "Fair"
        case .serious: thermalLabel = "Warm"
        case .critical: thermalLabel = "Hot"
        @unknown default: thermalLabel = "Unknown"
        }
    }
}
