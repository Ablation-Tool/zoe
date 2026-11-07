import SwiftUI

struct RootView: View {
    @State private var selection = 0

    var body: some View {
        TabView(selection: $selection) {
            GuidedVisionView(selection: $selection)
                .tabItem { Label("Vision", systemImage: "eye") }
                .tag(0)
            VolumeView()
                .tabItem { Label("Volume", systemImage: "chart.bar") }
                .tag(1)
            DeviceView()
                .tabItem { Label("Device", systemImage: "battery.100") }
                .tag(2)
            ConversationView()
                .tabItem { Label("Talk", systemImage: "waveform") }
                .tag(3)
            SafeConvertView()
                .tabItem { Label("Help", systemImage: "heart") }
                .tag(4)
        }
        .tint(Color(red: 103 / 255, green: 232 / 255, blue: 249 / 255))
        .preferredColorScheme(.dark)
    }
}
