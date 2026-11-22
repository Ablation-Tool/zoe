import SwiftUI

/// Adaptive root for iPhone, iPhone Duo / Fold (folded cover vs unfolded canvas), and iPad.
/// - Compact width (iPhone, folded outer display): NavigationStack over the Google Gemini-inspired Home.
/// - Regular width (unfolded inner display, iPad): NavigationSplitView keeping sidebar cleanly
///   to one side of the fold crease so no control ever spans the hinge.
/// Selected Zapp is preserved per scene via @SceneStorage across folding, unfolding, and resizing.
struct RootView: View {
    @AppStorage(ZoeticTheme.storageKey) private var themeRaw = ZoeticTheme.system.rawValue
    @SceneStorage("zoe.selectedZapp") private var selectedRaw = ""
    @StateObject private var store = ZappOrderStore()
    @State private var path: [ZappID] = []
    @Environment(\.horizontalSizeClass) private var sizeClass
    @Environment(\.colorScheme) private var systemScheme

    private var theme: Binding<ZoeticTheme> {
        Binding(
            get: { ZoeticTheme(rawValue: themeRaw) ?? .system },
            set: { themeRaw = $0.rawValue }
        )
    }

    private var selected: ZappID? {
        ZappID(rawValue: selectedRaw)
    }

    var body: some View {
        Group {
            if sizeClass == .regular {
                splitLayout
            } else {
                stackLayout
            }
        }
        .tint(GemPalette.cobalt)
        .preferredColorScheme(theme.wrappedValue.colorScheme)
        .onChange(of: sizeClass) { _, newValue in
            if newValue == .regular {
                if selectedRaw.isEmpty, let last = path.last { selectedRaw = last.rawValue }
            } else if let current = selected, path.isEmpty {
                path = [current]
            }
        }
    }

    private func goHome() {
        selectedRaw = ""
        path.removeAll()
    }

    private func openZapp(_ zapp: ZappID) {
        selectedRaw = zapp.rawValue
        if sizeClass != .regular {
            path = [zapp]
        }
    }

    // MARK: Compact (iPhone & folded iPhone Duo)

    private var stackLayout: some View {
        NavigationStack(path: $path) {
            DeskHomeView(store: store, theme: theme) { zapp in
                selectedRaw = zapp.rawValue
                path = [zapp]
            }
            .navigationDestination(for: ZappID.self) { zapp in
                ZappScreen(zapp: zapp, selection: selectionBinding, onGoHome: goHome, onOpenZapp: openZapp)
                    .navigationTitle(zapp.title)
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button(action: goHome) {
                                Image("RubySprout")
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 28, height: 28)
                            }
                            .accessibilityLabel("Return to Zoe home")
                        }
                    }
            }
        }
    }

    // MARK: Regular (unfolded iPhone Duo & iPad)

    private var splitLayout: some View {
        NavigationSplitView {
            List {
                Section {
                    ForEach(store.order) { zapp in
                        Button {
                            selectedRaw = zapp.rawValue
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: zapp.systemImage)
                                    .foregroundStyle(zapp.accent)
                                    .frame(width: 30, height: 30)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(zapp.title)
                                        .font(.body)
                                        .foregroundStyle(GemPalette.ink)
                                    Text(zapp.simpleHelper)
                                        .font(.caption)
                                        .foregroundStyle(GemPalette.muted)
                                        .lineLimit(1)
                                }
                            }
                            .frame(minHeight: 50, alignment: .leading)
                        }
                        .listRowBackground(
                            selected == zapp ? GemPalette.surface : Color.clear
                        )
                        .accessibilityAddTraits(selected == zapp ? [.isSelected] : [])
                    }
                } header: {
                    Button(action: goHome) {
                        HStack(spacing: 8) {
                            Image("RubySprout")
                                .resizable()
                                .scaledToFit()
                                .frame(width: 22, height: 22)
                            Text("Zoe · Offline")
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(GemPalette.ink)
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Return to Zoe home")
                }
                Section {
                    Button {
                        theme.wrappedValue = theme.wrappedValue.toggled(from: systemScheme)
                    } label: {
                        Label("Appearance: \(theme.wrappedValue.label)", systemImage: "circle.lefthalf.filled")
                            .frame(minHeight: 48, alignment: .leading)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(GeminiAmbientBackdrop())
            .navigationTitle("Zoe")
        } detail: {
            if let zapp = selected {
                ZappScreen(zapp: zapp, selection: selectionBinding, onGoHome: goHome, onOpenZapp: openZapp)
                    .navigationTitle(zapp.title)
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button(action: goHome) {
                                Image("RubySprout")
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 28, height: 28)
                            }
                            .accessibilityLabel("Return to Zoe home")
                        }
                    }
            } else {
                DeskHomeView(store: store, theme: theme) { zapp in
                    selectedRaw = zapp.rawValue
                }
            }
        }
    }

    private var selectionBinding: Binding<Int> {
        Binding(
            get: {
                switch selected {
                case .some(.trinity): return 1
                case .some(.device): return 2
                default: return 0
                }
            },
            set: { index in
                let target: ZappID
                switch index {
                case 1: target = .trinity
                case 2: target = .device
                default: target = .vision
                }
                selectedRaw = target.rawValue
                if sizeClass != .regular { path = [target] }
            }
        )
    }
}

/// Clean native Zapp host (zero retro chrome).
struct ZappScreen: View {
    let zapp: ZappID
    @Binding var selection: Int
    var onGoHome: () -> Void = {}
    var onOpenZapp: (ZappID) -> Void = { _ in }

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .gemScreen()
    }

    @ViewBuilder
    private var content: some View {
        switch zapp {
        case .vision: GuidedVisionView(selection: $selection)
        case .talk: ConversationView(onGoHome: onGoHome, onOpenMapsSafety: { onOpenZapp(.maps) })
        case .live: ZoeLiveView()
        case .creative: CreativeStudioView()
        case .arcade: ZoeArcadeView()
        case .vault: PrivacyVaultView()
        case .maps: MapsSafetyView(onOpenSafeConvert: { onOpenZapp(.safeconvert) })
        case .volume: VolumeView()
        case .trinity: TrinityView()
        case .device: DeviceView()
        case .safeconvert: SafeConvertView().ignoresSafeArea(edges: .bottom)
        }
    }
}
