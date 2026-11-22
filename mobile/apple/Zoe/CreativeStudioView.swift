import PhotosUI
import SwiftUI

/// Zoe Creative Studio — Scientific-Aesthetic Image Lab & Story Preview for Apple (v0.9.0-beta).
/// Grounds visual synthesis on Ernst Haeckel, August Weismann, Jean-Baptiste Lamarck & Google Patents schematics.
struct CreativeStudioView: View {
    @State private var spec = CreativeAndArcadeCore.ImageEditSpec()
    @State private var baseline: ScientificVisualAndPatentCore.BaselinePlate = .atelier
    @State private var commandText = ""
    @State private var statusText = "Edit Zoe's Atelier canvas, generate a scientific plate, or pick any photo — 100% offline."
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
                            ScientificPlateCanvasView(plate: baseline, concept: commandText)
                        }
                    }
                    .frame(height: 240)
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

                VStack(alignment: .leading, spacing: 3) {
                    Text(statusText)
                        .font(.caption)
                        .foregroundStyle(GemPalette.cobalt)
                    Text("Baseline: \(baseline.lineage) · \(baseline.mathSummary)")
                        .font(.caption2)
                        .foregroundStyle(GemPalette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                // Scientific-Aesthetic Baseline Plates (Haeckel · Weismann · Lamarck · Google Patents)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(ScientificVisualAndPatentCore.BaselinePlate.allCases) { plate in
                            Button(plate.rawValue) {
                                loadedImage = nil
                                baseline = plate
                                statusText = "Rendered factual baseline: \(plate.lineage) (100% offline math)."
                            }
                            .buttonStyle(GemKeycapButtonStyle(accent: baseline == plate ? GemPalette.emerald : GemPalette.muted))
                        }
                    }
                }

                HStack(spacing: 8) {
                    TextField("e.g. haeckel, patent, warm, rotate, blur, caption Sunset…", text: $commandText)
                        .textFieldStyle(.plain)
                        .padding(10)
                    Button("Apply") {
                        let lower = commandText.lowercased()
                        if lower.contains("haeckel") || lower.contains("radiolaria") {
                            loadedImage = nil
                            baseline = .haeckelRadiolaria
                            statusText = "Rendered Ernst Haeckel Kunstformen der Natur plate."
                        } else if lower.contains("ammonite") || lower.contains("spiral") {
                            loadedImage = nil
                            baseline = .haeckelAmmonite
                            statusText = "Rendered Haeckel logarithmic ammonite spiral plate."
                        } else if lower.contains("weismann") || lower.contains("mitosis") {
                            loadedImage = nil
                            baseline = .weismannGermplasm
                            statusText = "Rendered August Weismann cytological plate."
                        } else if lower.contains("lamarck") || lower.contains("morphospace") {
                            loadedImage = nil
                            baseline = .lamarckMorphospace
                            statusText = "Rendered Jean-Baptiste Lamarck morphospace plate."
                        } else if lower.contains("patent") || lower.contains("blueprint") || lower.contains("schematic") {
                            loadedImage = nil
                            baseline = .patentBlueprint
                            statusText = "Rendered orthographic patent schematic plate."
                        } else {
                            spec = CreativeAndArcadeCore.parseImageEditCommand(commandText, current: spec)
                            statusText = "Applied: \(spec.filter.rawValue) · rot \(spec.rotationDeg)°"
                        }
                        commandText = ""
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
                        baseline = .atelier
                        loadedImage = nil
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

/// Deterministic offline SwiftUI Canvas renderer mirroring Android's ScientificVisualSubstrate.java.
private struct ScientificPlateCanvasView: View {
    let plate: ScientificVisualAndPatentCore.BaselinePlate
    let concept: String

    var body: some View {
        let seed = ScientificVisualAndPatentCore.deterministicSeed(concept)
        switch plate {
        case .atelier:
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
        case .haeckelRadiolaria:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.96, green: 0.94, blue: 0.88)))
                let cx = size.width / 2
                let cy = size.height / 2
                let maxR = min(size.width, size.height) * 0.38
                let order = ScientificVisualAndPatentCore.symmetryOrder(forSeed: seed)
                for i in 0..<order {
                    let a = 2.0 * .pi * Double(i) / Double(order)
                    var line = Path()
                    line.move(to: CGPoint(x: cx, y: cy))
                    line.addLine(to: CGPoint(x: cx + cos(a) * maxR, y: cy + sin(a) * maxR))
                    ctx.stroke(line, with: .color(i % 2 == 0 ? Color(red: 0.11, green: 0.36, blue: 0.42) : Color(red: 0.72, green: 0.29, blue: 0.22)), lineWidth: 2)
                }
                for k in 1...72 {
                    let pt = ScientificVisualAndPatentCore.phyllotaxisPoint(index: k, scale: maxR * 0.05)
                    let dot = CGRect(x: cx + pt.x - 2.5, y: cy + pt.y - 2.5, width: 5, height: 5)
                    ctx.fill(Path(ellipseIn: dot), with: .color(k % 3 == 0 ? Color(red: 0.78, green: 0.60, blue: 0.23) : Color(red: 0.11, green: 0.36, blue: 0.42)))
                }
            }
        case .haeckelAmmonite:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.06, green: 0.09, blue: 0.13)))
                let cx = size.width / 2
                let cy = size.height / 2
                var spiral = Path()
                for i in 0...180 {
                    let t = Double(i) / 180.0 * 5.2 * .pi
                    let pt = ScientificVisualAndPatentCore.logarithmicSpiralPoint(thetaRad: t, a: 3.0, b: 0.19)
                    let cg = CGPoint(x: cx + pt.x, y: cy + pt.y)
                    if i == 0 { spiral.move(to: cg) } else { spiral.addLine(to: cg) }
                }
                ctx.stroke(spiral, with: .color(Color(red: 0.93, green: 0.89, blue: 0.79)), lineWidth: 2.2)
            }
        case .weismannGermplasm:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.96, green: 0.95, blue: 0.91)))
                let oval = CGRect(x: size.width * 0.14, y: size.height * 0.18, width: size.width * 0.72, height: size.height * 0.64)
                ctx.stroke(Path(ellipseIn: oval), with: .color(Color(red: 0.16, green: 0.15, blue: 0.20)), lineWidth: 2)
                for i in -5...5 {
                    var arc = Path()
                    arc.move(to: CGPoint(x: size.width * 0.24, y: size.height * 0.5))
                    arc.addQuadCurve(to: CGPoint(x: size.width * 0.76, y: size.height * 0.5),
                                     control: CGPoint(x: size.width * 0.5, y: size.height * 0.5 + Double(i) * 18))
                    ctx.stroke(arc, with: .color(Color(red: 0.17, green: 0.36, blue: 0.54).opacity(0.65)), lineWidth: 1.2)
                }
            }
        case .lamarckMorphospace:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.95, green: 0.93, blue: 0.86)))
                for i in 0..<5 {
                    let t = Double(i - 2) / 2.0
                    var branch = Path()
                    branch.move(to: CGPoint(x: size.width * 0.5, y: size.height * 0.85))
                    branch.addQuadCurve(to: CGPoint(x: size.width * (0.5 + t * 0.35), y: size.height * 0.25),
                                        control: CGPoint(x: size.width * (0.5 + t * 0.18), y: size.height * 0.58))
                    ctx.stroke(branch, with: .color(Color(red: 0.20, green: 0.22, blue: 0.18)), lineWidth: 2.2)
                }
            }
        case .patentBlueprint:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.06, green: 0.18, blue: 0.36)))
                let gx = size.width * 0.36
                let gy = size.height * 0.52
                let gr = min(size.width, size.height) * 0.24
                var gear = Path()
                let teeth = 14
                for i in 0..<(teeth * 2) {
                    let a = Double(i) * .pi / Double(teeth)
                    let r = (i % 2 == 0) ? gr * 1.12 : gr * 0.92
                    let pt = CGPoint(x: gx + cos(a) * r, y: gy + sin(a) * r)
                    if i == 0 { gear.move(to: pt) } else { gear.addLine(to: pt) }
                }
                gear.closeSubpath()
                ctx.stroke(gear, with: .color(.white), lineWidth: 2)
                var prism = Path()
                let px = size.width * 0.70
                prism.move(to: CGPoint(x: px, y: gy - gr))
                prism.addLine(to: CGPoint(x: px + gr * 0.9, y: gy + gr * 0.7))
                prism.addLine(to: CGPoint(x: px - gr * 0.9, y: gy + gr * 0.7))
                prism.closeSubpath()
                ctx.stroke(prism, with: .color(.white), lineWidth: 2)
            }
        }
    }
}
