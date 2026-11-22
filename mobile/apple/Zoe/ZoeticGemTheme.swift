import SwiftUI
import UIKit

// MARK: - Theme selection (System Light/Dark + 1-tap toggle)

enum ZoeticTheme: Int, CaseIterable {
    case system = 0
    case light = 1
    case dark = 2

    static let storageKey = "zoe.themeMode"

    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }

    var label: String {
        switch self {
        case .system: return "System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }

    func toggled(from active: ColorScheme) -> ZoeticTheme {
        active == .dark ? .light : .dark
    }
}

// MARK: - Google Gemini x Zoe Ergonomic Palette (WCAG AAA+)

private func zoeColor(light: UInt32, dark: UInt32) -> Color {
    Color(UIColor { trait in
        let value = trait.userInterfaceStyle == .dark ? dark : light
        return UIColor(
            red: CGFloat((value >> 16) & 0xFF) / 255,
            green: CGFloat((value >> 8) & 0xFF) / 255,
            blue: CGFloat(value & 0xFF) / 255,
            alpha: 1)
    })
}

enum GemPalette {
    static let paperDesk = zoeColor(light: 0xFFFFFF, dark: 0x0E0F12)
    static let surface = zoeColor(light: 0xF0F4F9, dark: 0x1E1F20)
    static let surfaceHigh = zoeColor(light: 0xE1E7F0, dark: 0x2A2B2F)
    static let hairline = zoeColor(light: 0xDCE1E8, dark: 0x33353A)
    static let ink = zoeColor(light: 0x1F1F1F, dark: 0xE8EAED)
    static let muted = zoeColor(light: 0x5F6368, dark: 0x9AA0A6)

    static let cobalt = zoeColor(light: 0x1A73E8, dark: 0x8AB4F8)     // DeepMind Blue
    static let ruby = zoeColor(light: 0xD62848, dark: 0xF43F5E)       // Zoe Living Ruby
    static let seafoam = zoeColor(light: 0x007B83, dark: 0x78D9EC)    // Calm Teal
    static let ochre = zoeColor(light: 0xB06000, dark: 0xFDD663)      // Warm Gold
    static let mulberry = zoeColor(light: 0x8430CE, dark: 0xD7AEFB)   // Soft Violet
    static let emerald = zoeColor(light: 0x137333, dark: 0x81C995)    // Botanical Green

    static let primaryButtonFill = zoeColor(light: 0x1A73E8, dark: 0x8AB4F8)
    static let primaryButtonInk = zoeColor(light: 0xFFFFFF, dark: 0x0E0F12)
    static let liveButtonFill = zoeColor(light: 0x1A73E8, dark: 0x1E3A7A)
    static let liveButtonInk = zoeColor(light: 0xFFFFFF, dark: 0xD2E3FC)

    /// Optical glass of the camera viewport stays dark in every theme.
    static let opticalGlass = Color(red: 12 / 255, green: 14 / 255, blue: 18 / 255)

    static let greetingGradient = LinearGradient(
        colors: [cobalt, mulberry, ruby],
        startPoint: .leading,
        endPoint: .trailing
    )
}

// MARK: - Zapps

enum ZappID: String, CaseIterable, Identifiable {
    case vision, talk, volume, trinity, device, safeconvert

    var id: String { rawValue }

    var title: String {
        switch self {
        case .vision: return "Guided vision"
        case .talk: return "Talk"
        case .volume: return "Accessible volume"
        case .trinity: return "Trinity"
        case .device: return "Device field"
        case .safeconvert: return "SafeConvert"
        }
    }

    var simpleHelper: String {
        switch self {
        case .vision: return "Look around & read aloud"
        case .talk: return "Speak or type calmly with Zoe"
        case .volume: return "Count open choices clearly"
        case .trinity: return "Link phone & computer"
        case .device: return "Battery & speaker check"
        case .safeconvert: return "Units & private safety helper"
        }
    }

    var systemImage: String {
        switch self {
        case .vision: return "eye"
        case .talk: return "waveform"
        case .volume: return "chart.bar"
        case .trinity: return "triangle"
        case .device: return "battery.100"
        case .safeconvert: return "arrow.left.arrow.right"
        }
    }

    var accent: Color {
        switch self {
        case .vision, .trinity: return GemPalette.cobalt
        case .talk, .safeconvert: return GemPalette.ruby
        case .volume, .device: return GemPalette.emerald
        }
    }
}

/// User-ordered Zapps, persisted locally in UserDefaults (never leaves the device).
final class ZappOrderStore: ObservableObject {
    private static let key = "zoe.zappOrder"
    @Published private(set) var order: [ZappID]

    init() {
        let saved = UserDefaults.standard.stringArray(forKey: ZappOrderStore.key) ?? []
        var resolved = saved.compactMap { ZappID(rawValue: $0) }
        for id in ZappID.allCases where !resolved.contains(id) {
            resolved.append(id)
        }
        order = resolved
    }

    func moveToTop(_ id: ZappID) {
        guard let index = order.firstIndex(of: id), index > 0 else { return }
        var next = order
        next.remove(at: index)
        next.insert(id, at: 0)
        commit(next)
    }

    func moveUp(_ id: ZappID) {
        guard let index = order.firstIndex(of: id), index > 0 else { return }
        var next = order
        next.swapAt(index, index - 1)
        commit(next)
    }

    func moveDown(_ id: ZappID) {
        guard let index = order.firstIndex(of: id), index < order.count - 1 else { return }
        var next = order
        next.swapAt(index, index + 1)
        commit(next)
    }

    func reset() {
        commit(ZappID.allCases)
    }

    private func commit(_ next: [ZappID]) {
        order = next
        UserDefaults.standard.set(next.map { $0.rawValue }, forKey: ZappOrderStore.key)
    }
}

// MARK: - Ambient Google Gemini Backdrop & Ergonomic Styles

/// Calm ambient canvas: deep night with soft lower sapphire glow in Dark mode,
/// spotless white with a gentle pastel sky mist in Light mode.
struct GeminiAmbientBackdrop: View {
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        ZStack {
            GemPalette.paperDesk
            RadialGradient(
                colors: colorScheme == .dark
                    ? [
                        Color(red: 24 / 255, green: 48 / 255, blue: 108 / 255).opacity(0.45),
                        Color(red: 34 / 255, green: 30 / 255, blue: 82 / 255).opacity(0.18),
                        Color.clear
                    ]
                    : [
                        Color(red: 224 / 255, green: 236 / 255, blue: 255 / 255).opacity(0.55),
                        Color(red: 242 / 255, green: 246 / 255, blue: 255 / 255).opacity(0.22),
                        Color.clear
                    ],
                center: UnitPoint(x: 0.5, y: 0.82),
                startRadius: 10,
                endRadius: 420
            )
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

struct GemCardStyle: ViewModifier {
    var radius: CGFloat = 22

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(GemPalette.surface)
            )
    }
}

extension View {
    func gemCard(radius: CGFloat = 22) -> some View {
        modifier(GemCardStyle(radius: radius))
    }

    func gemScreen() -> some View {
        background(GeminiAmbientBackdrop())
    }
}

struct GemKeycapButtonStyle: ButtonStyle {
    var accent: Color = GemPalette.cobalt

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.medium))
            .foregroundStyle(GemPalette.ink)
            .frame(maxWidth: .infinity, minHeight: 50)
            .padding(.horizontal, 16)
            .background(
                Capsule(style: .continuous)
                    .fill(configuration.isPressed ? GemPalette.surfaceHigh : GemPalette.surface)
            )
            .opacity(configuration.isPressed ? 0.88 : 1)
    }
}

struct GemPrimaryButtonStyle: ButtonStyle {
    var accent: Color = GemPalette.primaryButtonFill
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.medium))
            .foregroundStyle(GemPalette.primaryButtonInk)
            .frame(maxWidth: .infinity, minHeight: 54)
            .padding(.horizontal, 18)
            .background(
                Capsule(style: .continuous)
                    .fill(accent.opacity(configuration.isPressed ? 0.82 : 1))
            )
            .opacity(isEnabled ? 1 : 0.42)
    }
}
