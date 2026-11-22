import PhotosUI
import SwiftUI

/// Zoe Creative Studio — Image Lab & Story Preview for Apple (v0.6.0-beta).
struct CreativeStudioView: View {
    @State private var spec = CreativeAndArcadeCore.ImageEditSpec()
    @State private var commandText = ""
    @State private var statusText = "Edit Zoe's Atelier canvas or pick any photo — 100% offline."
    @State private var pickedItem: PhotosPickerItem?
    @State private var loadedImage: UIImage?

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                ZStack(alignment: .bottom) {
                    Group {
                        if let uiImg = loadedImage {
                            Image(uiImage: uiImg)
                                .resizable()
                                .scaledToFit()
                        } else {
                            LinearGradient(
                                colors: [Color(red: 0.08, green: 0.14, blue: 0.28),
                                         Color(red: 0.15, green: 0.32, blue: 0.56),
                                         Color(red: 0.88, green: 0.52, blue: 0.38)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                            .overlay(
                                Circle()
                                    .fill(Color(red: 1.0, green: 0.90, blue: 0.68).opacity(0.85))
                                    .frame(width: 78, height: 78)
                                    .offset(x: 42, y: -12)
                            )
                        }
                    }
                    .frame(height: 230)
                    .frame(maxWidth: .infinity)
                    .clipped()
                    .saturation(saturationValue)
                    .contrast(spec.contrast)
                    .brightness(Double(spec.brightness) / 220.0)
                    .rotationEffect(.degrees(Double(spec.rotationDeg)))
                    .blur(radius: spec.privacyBlur ? 10 : 0)

                    if !spec.caption.isEmpty {
                        Text(spec.caption)
                            .font(.headline)
                            .foregroundStyle(.white)
                            .padding(.vertical, 8)
                            .frame(maxWidth: .infinity)
                            .background(Color.black.opacity(0.68))
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                .gemCard(radius: 22)

                Text(statusText)
                    .font(.caption)
                    .foregroundStyle(GemPalette.cobalt)
                    .frame(maxWidth: .infinity, alignment: .leading)

                HStack(spacing: 8) {
                    TextField("e.g. warm, noir, rotate, blur, caption Sunset…", text: $commandText)
                        .textFieldStyle(.plain)
                        .padding(10)
                    Button("Apply") {
                        spec = CreativeAndArcadeCore.parseImageEditCommand(commandText, current: spec)
                        commandText = ""
                        statusText = "Applied: \(spec.filter.rawValue) · rot \(spec.rotationDeg)°"
                    }
                    .buttonStyle(GemPrimaryButtonStyle())
                    .fixedSize()
                }
                .padding(6)
                .gemCard(radius: 22)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(CreativeAndArcadeCore.FilterPreset.allCases) { preset in
                            Button(preset.rawValue) {
                                spec.filter = preset
                                statusText = "Filter: \(preset.rawValue)"
                            }
                            .buttonStyle(GemKeycapButtonStyle(accent: spec.filter == preset ? GemPalette.cobalt : GemPalette.muted))
                        }
                    }
                }

                HStack(spacing: 8) {
                    Button("Rotate 90°") { spec.rotationDeg = (spec.rotationDeg + 90) % 360 }
                        .buttonStyle(GemKeycapButtonStyle())
                    Button(spec.privacyBlur ? "Privacy blur: on" : "Privacy blur: off") { spec.privacyBlur.toggle() }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ochre))
                }

                HStack(spacing: 8) {
                    PhotosPicker(selection: $pickedItem, matching: .images) {
                        Text("Pick Photo")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(GemPrimaryButtonStyle())
                    Button("Reset") {
                        spec = CreativeAndArcadeCore.ImageEditSpec()
                        statusText = "Reset all edits."
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                }
            }
            .padding(16)
        }
        .gemScreen()
        .onChange(of: pickedItem) { _, newItem in
            Task {
                if let data = try? await newItem?.loadTransferable(type: Data.self),
                   let img = UIImage(data: data) {
                    await MainActor.run {
                        loadedImage = img
                        statusText = "Loaded photo from library."
                    }
                }
            }
        }
    }

    private var saturationValue: Double {
        switch spec.filter {
        case .noirBW: return 0.0
        case .sepia: return 0.45
        case .vividPop: return 1.55
        default: return 1.0
        }
    }
}
