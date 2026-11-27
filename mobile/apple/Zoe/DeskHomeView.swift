import SwiftUI

/// Google Gemini-inspired ultra-simple, ergonomic Home screen for Zoe.
/// Built for effortless scanning and motor comfort for both adults and children with disabilities:
/// - Borderless top bar (= menu, "Zoe Offline", Light/Dark toggle, Zoe Living Spark)
/// - Calm breathing greeting ("Hi, I'm Zoe" / "Follow your curiosity.")
/// - Open borderless 62pt icon + plain-English action rows (zero visual box walls)
/// - Floating Gemini-style bottom action capsule (+ | Ask Zoe | Look | Live Talk)
struct DeskHomeView: View {
    @ObservedObject var store: ZappOrderStore
    @Binding var theme: ZoeticTheme
    var onOpen: (ZappID) -> Void
    var onOpenBrain: (String, String) -> Void = { _, _ in }
    var onAskBrainPrompt: (String) -> Void = { _ in }

    @State private var arranging = false
    @State private var showInfo = false
    @State private var showQuickSheet = false
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.horizontalSizeClass) private var sizeClass
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        topBar(scrollProxy: proxy)
                            .id("zoeHomeTop")
                        heroGreeting(scrollProxy: proxy)
                        dorothyBrainCenterpiece
                        brainQuickQuestionsStrip
                        if arranging {
                            arrangeList
                            modeToggleRow
                        } else {
                            zappActionList
                        }
                    }
                    .padding(.bottom, 16)
                    .frame(maxWidth: sizeClass == .regular ? 820 : .infinity)
                    .frame(maxWidth: .infinity)
                }
            }
            floatingGeminiCapsule
        }
        .background(GeminiAmbientBackdrop())
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $showInfo) {
            AboutZoeSheet(theme: theme)
                .presentationDetents([.medium])
        }
        .sheet(isPresented: $showQuickSheet) {
            QuickActionsSheet(
                arranging: $arranging,
                onOpenBrain: { onOpen(.brain) },
                onOpenMapsSafety: { onOpen(.maps) },
                onOpenSafeConvert: { onOpen(.safeconvert) },
                onOpenGemini: {
                    if let url = URL(string: "https://gemini.google.com") {
                        openURL(url)
                    }
                }
            )
            .presentationDetents([.medium])
        }
    }

    // MARK: Borderless Gemini Top Bar

    private func topBar(scrollProxy: ScrollViewProxy) -> some View {
        HStack(spacing: 6) {
            Button {
                showQuickSheet = true
            } label: {
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(GemPalette.ink)
                    .frame(width: 48, height: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Open quick menu")

            Button {
                showInfo = true
            } label: {
                HStack(spacing: 6) {
                    Text("Zoe")
                        .font(.system(size: 21, weight: .regular))
                        .foregroundStyle(GemPalette.ink)
                    Text("Beta")
                        .font(.system(size: 16, weight: .regular))
                        .foregroundStyle(GemPalette.muted)
                    Circle()
                        .fill(GemPalette.cobalt)
                        .frame(width: 7, height: 7)
                        .offset(y: -4)
                }
                .frame(minHeight: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("About Zoe")
            .accessibilityAddTraits(.isHeader)

            Spacer()

            Button {
                theme = theme.toggled(from: colorScheme)
            } label: {
                Image(systemName: colorScheme == .dark ? "sun.max" : "circle.lefthalf.filled")
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(GemPalette.ink)
                    .frame(width: 48, height: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(colorScheme == .dark ? "Switch to Light appearance" : "Switch to Dark appearance")

            Button {
                arranging = false
                withAnimation { scrollProxy.scrollTo("zoeHomeTop", anchor: .top) }
            } label: {
                Image("RubySprout")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 30, height: 30)
                    .frame(width: 48, height: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Return to Zoe home")
        }
        .padding(.horizontal, 12)
        .padding(.top, 4)
    }

    // MARK: Calm Breathing Hero with Zoe GEM-Ellipsis Anchor

    private func heroGreeting(scrollProxy: ScrollViewProxy) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Button {
                arranging = false
                withAnimation { scrollProxy.scrollTo("zoeHomeTop", anchor: .top) }
            } label: {
                Image("RubySprout")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 46, height: 46)
                    .frame(minWidth: 48, minHeight: 48, alignment: .leading)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 4)
            .accessibilityLabel("Zoe home")
            Text("Hi, I'm Zoe")
                .font(.system(size: 30, weight: .medium))
                .foregroundStyle(GemPalette.greetingGradient)
                .accessibilityAddTraits(.isHeader)
        }
        .padding(.horizontal, 24)
        .padding(.top, 12)
        .padding(.bottom, 12)
    }

    // MARK: CENTERPIECE Dorothy 3D Brain Observatory Hero Card

    private var dorothyHeroImage: UIImage? {
        if let dir = Bundle.main.url(forResource: "dorothy_brain_observatory", withExtension: nil) {
            if let img = UIImage(contentsOfFile: dir.appendingPathComponent("previews/hero_brain_card.jpg").path) { return img }
            if let img = UIImage(contentsOfFile: dir.appendingPathComponent("previews/01_hero_tissue.jpg").path) { return img }
        }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("dorothy_brain_observatory/previews/hero_brain_card.jpg"),
           let img = UIImage(contentsOfFile: res.path) {
            return img
        }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("dorothy_brain_observatory/previews/01_hero_tissue.jpg"),
           let img = UIImage(contentsOfFile: res.path) {
            return img
        }
        return nil
    }

    private var dorothyBrainCenterpiece: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                onOpenBrain("brain3d", "")
            } label: {
                let heroHeight: CGFloat = (sizeClass == .regular) ? 248 : 196
                ZStack(alignment: .bottomLeading) {
                    if let uiImg = dorothyHeroImage {
                        Image(uiImage: uiImg)
                            .resizable()
                            .scaledToFill()
                            .frame(height: heroHeight)
                            .clipped()
                    } else {
                        Color(red: 7 / 255, green: 11 / 255, blue: 18 / 255)
                            .frame(height: heroHeight)
                    }
                    LinearGradient(
                        colors: [
                            Color.black.opacity(0.08),
                            Color(red: 11 / 255, green: 17 / 255, blue: 29 / 255).opacity(0.95)
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Dorothy 3D Brain")
                            .font(.title2.weight(.bold))
                            .foregroundStyle(Color(red: 245 / 255, green: 208 / 255, blue: 120 / 255))
                    }
                    .padding(14)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Open Dorothy 3D Brain Observatory")

            VStack(spacing: 8) {
                Button {
                    onOpenBrain("brain3d", "")
                } label: {
                    Text("Explore Dorothy 3D Brain")
                        .font(.body.weight(.bold))
                        .foregroundStyle(Color(red: 7 / 255, green: 11 / 255, blue: 18 / 255))
                        .frame(maxWidth: .infinity, minHeight: 46)
                        .background(
                            Capsule(style: .continuous)
                                .fill(Color(red: 245 / 255, green: 208 / 255, blue: 120 / 255))
                        )
                }
                .buttonStyle(.plain)

                HStack(spacing: 8) {
                    Button {
                        onOpenBrain("askzoe", "")
                    } label: {
                        Text("Ask Zoe: Brain")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Color(red: 56 / 255, green: 189 / 255, blue: 248 / 255))
                            .frame(maxWidth: .infinity, minHeight: 42)
                            .background(
                                Capsule(style: .continuous)
                                    .fill(Color(red: 20 / 255, green: 29 / 255, blue: 46 / 255))
                            )
                    }
                    .buttonStyle(.plain)

                    Button {
                        onOpenBrain("media", "")
                    } label: {
                        Text("Videos & Gallery")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Color(red: 52 / 255, green: 211 / 255, blue: 153 / 255))
                            .frame(maxWidth: .infinity, minHeight: 42)
                            .background(
                                Capsule(style: .continuous)
                                    .fill(Color(red: 20 / 255, green: 29 / 255, blue: 46 / 255))
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(12)
            .background(Color(red: 11 / 255, green: 17 / 255, blue: 29 / 255))
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color(red: 245 / 255, green: 208 / 255, blue: 120 / 255).opacity(0.55), lineWidth: 1)
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 10)
    }

    private var brainQuickQuestionsStrip: some View {
        let items: [(String, String)] = [
            ("Broca's Area (BA 44)", "What does Broca's Area (BA 44) do?"),
            ("Hippocampus & Memory", "Where is the Hippocampus and what is its role?"),
            ("Cranial Nerve X (Vagus)", "Explain Cranial Nerve X (Vagus)"),
            ("Language Loop Circuit", "Explain the Language Loop neural circuit"),
            ("Circle of Willis & MCA", "What is the Circle of Willis and MCA territory?"),
            ("10-20 EEG Brain Waves", "How do 10-20 EEG brain waves work?")
        ]
        let columns = [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)]
        return VStack(alignment: .leading, spacing: 8) {
            Text("Ask Zoe about the brain")
                .font(.caption.weight(.semibold))
                .foregroundStyle(GemPalette.muted)
                .padding(.horizontal, 22)
            LazyVGrid(columns: columns, spacing: 8) {
                ForEach(items, id: \.0) { item in
                    Button {
                        onAskBrainPrompt(item.1)
                    } label: {
                        Text(item.0)
                            .font(.caption.weight(.medium))
                            .lineLimit(1)
                            .minimumScaleFactor(0.85)
                            .foregroundStyle(GemPalette.ink)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .padding(.horizontal, 10)
                            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(GemPalette.surface))
                            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(GemPalette.cobalt.opacity(0.35), lineWidth: 0.9))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
        }
        .padding(.bottom, 10)
    }

    // MARK: Focused Top 3 Ergonomic Hero Cards + Grouped More Zapps

    private var zappActionList: some View {
        let topThree = Array(store.order.prefix(3))
        let remaining = Array(store.order.dropFirst(3))
        return VStack(alignment: .leading, spacing: 10) {
            ForEach(topThree) { zapp in
                heroActionCard(zapp)
            }
            .padding(.horizontal, 16)

            modeToggleRow

            if !remaining.isEmpty {
                Text("More Zapps")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(GemPalette.muted)
                    .padding(.horizontal, 24)
                    .padding(.top, 18)
                    .accessibilityAddTraits(.isHeader)

                VStack(spacing: 0) {
                    ForEach(Array(remaining.enumerated()), id: \.element.id) { idx, zapp in
                        if idx > 0 {
                            Divider()
                                .overlay(GemPalette.hairline)
                                .padding(.leading, 72)
                                .padding(.trailing, 16)
                        }
                        actionRow(zapp)
                    }
                }
                .padding(.vertical, 6)
                .gemCard(radius: 24)
                .padding(.horizontal, 16)
            }
        }
    }

    private func heroActionCard(_ zapp: ZappID) -> some View {
        Button {
            onOpen(zapp)
        } label: {
            HStack(spacing: 16) {
                Image(systemName: zapp.systemImage)
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(zapp.accent)
                    .frame(width: 44, height: 44)
                    .background(Circle().fill(zapp.accent.opacity(colorScheme == .dark ? 0.16 : 0.10)))
                VStack(alignment: .leading, spacing: 2) {
                    Text(zapp.title)
                        .font(.system(size: 17.5, weight: .medium))
                        .foregroundStyle(GemPalette.ink)
                        .lineLimit(1)
                    Text(zapp.simpleHelper)
                        .font(.system(size: 13.5))
                        .foregroundStyle(GemPalette.muted)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(GemPalette.muted.opacity(0.6))
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity, minHeight: 74, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(GemPalette.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(GemPalette.hairline.opacity(0.55), lineWidth: 0.9)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(zapp.title). \(zapp.simpleHelper)")
        .accessibilityAddTraits(.isButton)
        .contextMenu { moveMenu(zapp) }
    }

    private func actionRow(_ zapp: ZappID) -> some View {
        Button {
            onOpen(zapp)
        } label: {
            HStack(spacing: 16) {
                Image(systemName: zapp.systemImage)
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(zapp.accent)
                    .frame(width: 42, height: 42)
                    .background(Circle().fill(zapp.accent.opacity(colorScheme == .dark ? 0.16 : 0.10)))
                VStack(alignment: .leading, spacing: 2) {
                    Text(zapp.title)
                        .font(.system(size: 17, weight: .regular))
                        .foregroundStyle(GemPalette.ink)
                        .lineLimit(1)
                    Text(zapp.simpleHelper)
                        .font(.system(size: 13.5))
                        .foregroundStyle(GemPalette.muted)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(zapp.title). \(zapp.simpleHelper)")
        .accessibilityAddTraits(.isButton)
        .contextMenu { moveMenu(zapp) }
    }

    // MARK: Arrange Mode (48pt ergonomic controls)

    private var arrangeList: some View {
        VStack(spacing: 8) {
            Text("Tap ★ to pin #1, or ↑ ↓ to move any Zapp.")
                .font(.footnote)
                .foregroundStyle(GemPalette.muted)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.bottom, 4)
            ForEach(Array(store.order.enumerated()), id: \.element.id) { index, zapp in
                HStack(spacing: 8) {
                    Image(systemName: zapp.systemImage)
                        .foregroundStyle(zapp.accent)
                        .frame(width: 38, height: 38)
                        .background(Circle().fill(zapp.accent.opacity(0.14)))
                    Text(zapp.title)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundStyle(GemPalette.ink)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    moveChip("★", label: "Pin \(zapp.title) to top", enabled: index > 0) { store.moveToTop(zapp) }
                    moveChip("↑", label: "Move \(zapp.title) up", enabled: index > 0) { store.moveUp(zapp) }
                    moveChip("↓", label: "Move \(zapp.title) down", enabled: index < store.order.count - 1) { store.moveDown(zapp) }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .frame(minHeight: 60)
                .gemCard(radius: 20)
            }
        }
        .padding(.horizontal, 16)
    }

    private func moveChip(_ symbol: String, label: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(symbol)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(GemPalette.ink)
                .frame(width: 48, height: 48)
                .background(Circle().fill(GemPalette.surfaceHigh))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.28)
        .accessibilityLabel(label)
    }

    // MARK: Gemini-Style Explore | Arrange Mode Toggle

    private var modeToggleRow: some View {
        HStack(spacing: 8) {
            Spacer()
            modePill("Explore", active: !arranging) {
                arranging = false
            }
            modePill(arranging ? "Done" : "Arrange", active: arranging) {
                arranging.toggle()
            }
            if arranging {
                Button("Reset") {
                    store.reset()
                }
                .font(.subheadline.weight(.medium))
                .foregroundStyle(GemPalette.ruby)
                .padding(.horizontal, 16)
                .frame(minHeight: 44)
            }
            Spacer()
        }
        .padding(.top, 14)
        .padding(.horizontal, 16)
    }

    private func modePill(_ title: String, active: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(active ? GemPalette.ink : GemPalette.muted)
                .padding(.horizontal, 20)
                .frame(minHeight: 44)
                .background(
                    Capsule(style: .continuous)
                        .fill(active ? GemPalette.surface : Color.clear)
                )
                .overlay(
                    Capsule(style: .continuous)
                        .stroke(active ? GemPalette.hairline : Color.clear, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }

    // MARK: Signature Floating Google Gemini Bottom Action Capsule

    private var floatingGeminiCapsule: some View {
        HStack(spacing: 6) {
            Button {
                showQuickSheet = true
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 21, weight: .regular))
                    .foregroundStyle(GemPalette.ink)
                    .frame(width: 48, height: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("More tools and quick actions")

            Button {
                onOpen(.talk)
            } label: {
                Text("Ask Zoe")
                    .font(.system(size: 17.5))
                    .foregroundStyle(GemPalette.muted)
                    .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
                    .padding(.leading, 4)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Ask or talk with Zoe")

            Button {
                onOpen(.vision)
            } label: {
                Image(systemName: "eye")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(GemPalette.ink)
                    .frame(width: 48, height: 48)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Open camera to look and read")

            Button {
                onOpen(.live)
            } label: {
                Image(systemName: "waveform")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(GemPalette.liveButtonInk)
                    .frame(width: 48, height: 48)
                    .background(Circle().fill(GemPalette.liveButtonFill))
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Open Zoe Explore live voice orb")
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(minHeight: 64)
        .background(
            Capsule(style: .continuous)
                .fill(GemPalette.surface)
        )
        .overlay(
            Capsule(style: .continuous)
                .stroke(GemPalette.hairline.opacity(0.6), lineWidth: 0.8)
        )
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 12)
    }

    @ViewBuilder
    private func moveMenu(_ zapp: ZappID) -> some View {
        Button("Pin to top (#1)") { store.moveToTop(zapp) }
        Button("Move up") { store.moveUp(zapp) }
        Button("Move down") { store.moveDown(zapp) }
        Button(arranging ? "Done arranging" : "Arrange Zapps") { arranging.toggle() }
    }
}

/// Clean Quick Actions sheet (opened from top '=' or bottom '+').
struct QuickActionsSheet: View {
    @Binding var arranging: Bool
    var onOpenBrain: () -> Void
    var onOpenMapsSafety: () -> Void
    var onOpenSafeConvert: () -> Void
    var onOpenGemini: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Quick actions")
                .font(.title3.weight(.semibold))
                .foregroundStyle(GemPalette.ink)
                .padding(.bottom, 4)
                .accessibilityAddTraits(.isHeader)

            quickRow("Dorothy 3d brain", helper: "interactive mni152 3d brain, live mri & atlas", icon: "brain.head.profile", accent: GemPalette.ochre) {
                dismiss()
                onOpenBrain()
            }
            quickRow("Maps & Safety", helper: "GPS, Apple & Google Maps", icon: "map", accent: GemPalette.seafoam) {
                dismiss()
                onOpenMapsSafety()
            }
            quickRow("SafeConvert", helper: "Units & private safety", icon: "arrow.left.arrow.right", accent: GemPalette.ruby) {
                dismiss()
                onOpenSafeConvert()
            }
            quickRow(arranging ? "Done arranging" : "Arrange Zapps", helper: "Put your favorites at the top", icon: "arrow.up.arrow.down", accent: GemPalette.ochre) {
                arranging.toggle()
                dismiss()
            }
            quickRow("Google Gemini", helper: "Open Gemini when you choose", icon: "sparkles", accent: GemPalette.cobalt) {
                dismiss()
                onOpenGemini()
            }
            Spacer(minLength: 8)
            Button("Close") { dismiss() }
                .buttonStyle(GemKeycapButtonStyle())
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(GemPalette.paperDesk.ignoresSafeArea())
    }

    private func quickRow(_ title: String, helper: String, icon: String, accent: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 18, weight: .medium))
                    .foregroundStyle(accent)
                    .frame(width: 42, height: 42)
                    .background(Circle().fill(accent.opacity(0.14)))
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body.weight(.medium)).foregroundStyle(GemPalette.ink)
                    Text(helper).font(.footnote).foregroundStyle(GemPalette.muted)
                }
                Spacer()
            }
            .frame(minHeight: 56)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// Clean About Zoe sheet.
struct AboutZoeSheet: View {
    let theme: ZoeticTheme
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                Image("RubySprout")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 44, height: 44)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Zoe (beta)")
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(GemPalette.ink)
                        .accessibilityAddTraits(.isHeader)
                    Text("v0.9.6-beta · Offline-first & free")
                        .font(.footnote)
                        .foregroundStyle(GemPalette.muted)
                }
            }
            Text("Privacy and dignity by design. Nothing listens, watches, saves, or uploads until you tap.")
                .font(.body)
                .foregroundStyle(GemPalette.ink)
            Text("Built for everyone: calm, clear, and accessible.\nAppearance: \(theme.label)")
                .font(.footnote)
                .foregroundStyle(GemPalette.muted)
            Spacer(minLength: 8)
            Button("Done") { dismiss() }
                .buttonStyle(GemPrimaryButtonStyle())
        }
        .padding(22)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(GemPalette.paperDesk.ignoresSafeArea())
    }
}
