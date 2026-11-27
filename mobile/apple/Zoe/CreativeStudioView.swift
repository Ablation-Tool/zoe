import PhotosUI
import SwiftUI

/// Zoe Creative Studio — Scientific-Aesthetic Image Lab & Story Preview for Apple (v0.9.0-beta).
/// Grounds visual synthesis on Ernst Haeckel, August Weismann, Jean-Baptiste Lamarck & Google Patents schematics.
struct CreativeStudioView: View {
    @State private var spec = CreativeAndArcadeCore.ImageEditSpec()
    @State private var undoStack: [CreativeAndArcadeCore.ImageEditSpec] = []
    @State private var baseline: ScientificVisualAndPatentCore.BaselinePlate = .atelier
    @State private var commandText = ""
    @State private var statusText = "Hold preview to compare original · 10 HD plates offline."
    @State private var pickedItem: PhotosPickerItem?
    @State private var loadedImage: UIImage?
    @State private var showTuneSliders = false
    @State private var comparingOriginal = false

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
                    .saturation(comparingOriginal ? 1.0 : (saturationValue * spec.saturation))
                    .contrast(comparingOriginal ? 1.0 : spec.contrast)
                    .brightness(comparingOriginal ? 0.0 : (Double(spec.brightness) / 220.0))
                    .scaleEffect(x: (!comparingOriginal && spec.flipHorizontal) ? -1.0 : 1.0, y: 1.0)
                    .rotationEffect(.degrees(comparingOriginal ? 0.0 : Double(spec.rotationDeg)))
                    .blur(radius: (!comparingOriginal && spec.privacyBlur) ? 10 : 0)

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
                    TextField("Try warm, chladni, blur, caption…", text: $commandText)
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
                        } else if lower.contains("chladni") || lower.contains("cymatic") || lower.contains("nodal") {
                            loadedImage = nil
                            baseline = .chladniPlate
                            statusText = "Rendered Ernst Chladni standing-wave nodal plate."
                        } else if lower.contains("phyllotaxis") || lower.contains("fibonacci") || lower.contains("sunflower") {
                            loadedImage = nil
                            baseline = .fibonacciPhyllotaxis
                            statusText = "Rendered golden-angle Fibonacci phyllotaxis plate."
                        } else if lower.contains("voronoi") || lower.contains("crystal") || lower.contains("mosaic") {
                            loadedImage = nil
                            baseline = .voronoiCrystal
                            statusText = "Rendered Georgy Voronoi cellular crystal tessellation plate."
                        } else if lower.contains("lissajous") || lower.contains("harmonic") || lower.contains("orbit") {
                            loadedImage = nil
                            baseline = .lissajousOrbit
                            statusText = "Rendered Jules Lissajous harmonic phase curve plate."
                        } else {
                            undoStack.append(spec)
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
                    Button(undoStack.isEmpty ? "Undo" : "Undo (\(undoStack.count))") {
                        if let prev = undoStack.popLast() { spec = prev }
                    }
                    .disabled(undoStack.isEmpty)
                    .buttonStyle(GemKeycapButtonStyle())
                    Button("Rotate 90°") {
                        undoStack.append(spec)
                        spec.rotationDeg = (spec.rotationDeg + 90) % 360
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                    Button(spec.flipHorizontal ? "Flip: on" : "Flip ↔") {
                        undoStack.append(spec)
                        spec.flipHorizontal.toggle()
                    }
                    .buttonStyle(GemKeycapButtonStyle(accent: spec.flipHorizontal ? GemPalette.cobalt : GemPalette.muted))
                    Button(spec.privacyBlur ? "Blur: on" : "Blur: off") {
                        undoStack.append(spec)
                        spec.privacyBlur.toggle()
                    }
                    .buttonStyle(GemKeycapButtonStyle(accent: spec.privacyBlur ? GemPalette.ochre : GemPalette.muted))
                }

                DisclosureGroup("Tune Sliders (Brightness · Contrast · Saturation)", isExpanded: $showTuneSliders) {
                    VStack(spacing: 8) {
                        HStack {
                            Text("Brightness \(spec.brightness)").font(.caption)
                            Slider(value: Binding(get: { Double(spec.brightness) }, set: { spec.brightness = Int($0) }), in: -60...60)
                        }
                        HStack {
                            Text(String(format: "Contrast %.1fx", spec.contrast)).font(.caption)
                            Slider(value: $spec.contrast, in: 0.5...1.8)
                        }
                        HStack {
                            Text("Saturation \(Int(spec.saturation * 100))%").font(.caption)
                            Slider(value: $spec.saturation, in: 0.0...2.0)
                        }
                    }
                    .padding(.top, 6)
                }
                .padding(12)
                .gemCard(radius: 18)

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
        case .matteFilm: return 0.78
        case .goldenHour: return 1.24
        case .cyberNeon: return 1.65
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
        case .chladniPlate:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.05, green: 0.06, blue: 0.10)))
                let modes = ScientificVisualAndPatentCore.chladniModes(forSeed: seed)
                let grid = 48
                let side = min(size.width, size.height) * 0.78
                let ox = (size.width - side) / 2
                let oy = (size.height - side) / 2
                let cell = side / Double(grid)
                for gy in 0..<grid {
                    let ny = (Double(gy) + 0.5) / Double(grid)
                    for gx in 0..<grid {
                        let nx = (Double(gx) + 0.5) / Double(grid)
                        let val = cos(Double(modes.m) * .pi * nx) * cos(Double(modes.n) * .pi * ny)
                            - cos(Double(modes.n) * .pi * nx) * cos(Double(modes.m) * .pi * ny)
                        let nodal = max(0.0, 1.0 - abs(val) * 4.0)
                        if nodal > 0.18 {
                            let r = cell * (0.32 + nodal * 0.32)
                            let rect = CGRect(x: ox + (Double(gx) + 0.5) * cell - r, y: oy + (Double(gy) + 0.5) * cell - r, width: r * 2, height: r * 2)
                            ctx.fill(Path(ellipseIn: rect), with: .color(Color(red: 0.95, green: 0.78, blue: 0.45).opacity(nodal)))
                        }
                    }
                }
            }
        case .fibonacciPhyllotaxis:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.97, green: 0.95, blue: 0.91)))
                let cx = size.width / 2
                let cy = size.height / 2
                let maxR = min(size.width, size.height) * 0.40
                let scale = maxR / sqrt(140.0)
                for k in 1...140 {
                    let pt = ScientificVisualAndPatentCore.phyllotaxisPoint(index: k, scale: scale)
                    let frac = Double(k) / 140.0
                    let r = 2.2 + frac * 3.2
                    let rect = CGRect(x: cx + pt.x - r, y: cy + pt.y - r, width: r * 2, height: r * 2)
                    ctx.fill(Path(ellipseIn: rect), with: .color(Color(red: 0.22 + 0.62 * frac, green: 0.48 + 0.18 * frac, blue: 0.34 - 0.10 * frac)))
                }
            }
        case .voronoiCrystal:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.05, green: 0.07, blue: 0.12)))
                let sites: [(Double, Double, Color)] = (0..<14).map { i in
                    let h1 = Double((seed &* 31 &+ i &* 97) % 1000) / 1000.0
                    let h2 = Double((seed &* 53 &+ i &* 131) % 1000) / 1000.0
                    let palette: [Color] = [
                        Color(red: 0.14, green: 0.34, blue: 0.56),
                        Color(red: 0.12, green: 0.46, blue: 0.44),
                        Color(red: 0.42, green: 0.24, blue: 0.48),
                        Color(red: 0.58, green: 0.42, blue: 0.18),
                    ]
                    return (0.1 + h1 * 0.8, 0.1 + h2 * 0.8, palette[i % palette.count])
                }
                let cols = 38
                let rows = 26
                let cw = size.width / Double(cols)
                let ch = size.height / Double(rows)
                for gy in 0..<rows {
                    let ny = (Double(gy) + 0.5) / Double(rows)
                    for gx in 0..<cols {
                        let nx = (Double(gx) + 0.5) / Double(cols)
                        var d1 = Double.greatestFiniteMagnitude
                        var d2 = Double.greatestFiniteMagnitude
                        var best = 0
                        for (idx, s) in sites.enumerated() {
                            let d = hypot(nx - s.0, ny - s.1)
                            if d < d1 { d2 = d1; d1 = d; best = idx }
                            else if d < d2 { d2 = d }
                        }
                        let edge = (d2 - d1) < 0.022
                        let rect = CGRect(x: Double(gx) * cw, y: Double(gy) * ch, width: cw + 0.8, height: ch + 0.8)
                        ctx.fill(Path(rect), with: .color(edge ? Color(red: 0.94, green: 0.80, blue: 0.46) : sites[best].2.opacity(0.88)))
                    }
                }
            }
        case .lissajousOrbit:
            Canvas { ctx, size in
                ctx.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color(red: 0.04, green: 0.05, blue: 0.09)))
                let ratios = ScientificVisualAndPatentCore.lissajousRatios(forSeed: seed)
                let cx = size.width / 2
                let cy = size.height / 2
                let rx = size.width * 0.40
                let ry = size.height * 0.38
                for layer in 0..<3 {
                    let phase = Double(layer) * 0.42 + .pi / 4.0
                    var curve = Path()
                    for i in 0...320 {
                        let t = Double(i) / 320.0 * 2.0 * .pi
                        let pt = CGPoint(x: cx + rx * sin(Double(ratios.a) * t + phase),
                                         y: cy + ry * sin(Double(ratios.b) * t))
                        if i == 0 { curve.move(to: pt) } else { curve.addLine(to: pt) }
                    }
                    let col = layer == 0 ? Color(red: 0.34, green: 0.82, blue: 0.94)
                        : (layer == 1 ? Color(red: 0.94, green: 0.76, blue: 0.44) : Color(red: 0.86, green: 0.44, blue: 0.62))
                    ctx.stroke(curve, with: .color(col.opacity(0.85)), lineWidth: 2.0 - Double(layer) * 0.3)
                }
            }
        }
    }
}
