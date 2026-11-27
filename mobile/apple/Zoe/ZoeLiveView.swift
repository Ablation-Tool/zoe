import ARKit
import SceneKit
import SwiftUI

/// Zoe Explore — Simultaneous Live Camera, Native ARKit 3D Space Companion & Continuous Voice for Apple (v0.7.0-beta).
struct ZoeLiveView: View {
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @StateObject private var camera = CameraController()
    @StateObject private var nativeVoice = ZoeNativeVoice()
    @State private var brain = ZoeBrainEngine(defaults: .standard)

    @State private var active = false
    @State private var hiZoeMode = false
    @State private var cameraOn = false
    @State private var arModeOn = false
    @State private var arRoamOn = true
    @State private var arStatus = "● AR · 1.2m"
    @State private var pulse = false
    @State private var useNativeVoice = false
    @State private var showToolsSheet = false
    @State private var a11yProfile: ArExploreCore.AccessibilityProfile = .standard
    @State private var kidMode = false
    @State private var typedMessage = ""
    @State private var caption = "Hi, I'm Zoe. Tap ✦ AR to explore together or tap Talk."
    @State private var stateLabel = "TAP ZOE TO TALK · MIC & CAMERA OFF"

    var body: some View {
        let fullScreen = cameraOn || arModeOn
        let largeCaptions = a11yProfile != .standard || kidMode
        ZStack {
            // Layer 0: True edge-to-edge full-screen Camera / ARKit stage
            if arModeOn {
                ZoeArKitSpaceView(roamEnabled: $arRoamOn, statusText: $arStatus) { spotted in
                    let q = a11yProfile == .blindLowVision
                        ? ArExploreCore.formatGuidedSceneCue(
                            primaryLabel: spotted.primaryLabel,
                            ocrSnippet: spotted.ocrSnippet,
                            normalizedX: 0,
                            distanceMeters: spotted.distanceMeters,
                            kidFriendly: kidMode
                        )
                        : ArExploreCore.buildCuriousQuestion(for: spotted)
                    caption = q
                    if a11yProfile != .deafHoH {
                        speakClean(q)
                    }
                }
                .ignoresSafeArea()
            } else if cameraOn {
                CameraPreview(session: camera.session)
                    .ignoresSafeArea()
            }

            if fullScreen {
                VStack(spacing: 0) {
                    LinearGradient(
                        colors: [Color.black.opacity(0.55), Color.clear],
                        startPoint: .top, endPoint: .bottom
                    )
                    .frame(height: 112)
                    Spacer()
                    LinearGradient(
                        colors: [Color.black.opacity(0.68), Color.clear],
                        startPoint: .bottom, endPoint: .top
                    )
                    .frame(height: 185)
                }
                .ignoresSafeArea()
                .allowsHitTesting(false)
            }

            // Layer 1: Calm, Minimal Foreground Chrome (focus on the screen!)
            VStack(spacing: 12) {
                HStack(spacing: 8) {
                    Text(arModeOn ? arStatus : (cameraOn ? "● Live" : "Zoe Explore"))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(.ultraThinMaterial, in: Capsule())
                    Spacer()
                    Button {
                        showToolsSheet = true
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                            .font(.body.weight(.semibold))
                            .foregroundStyle(.white)
                            .frame(width: 40, height: 40)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Open Zoe Explore tools and accessibility settings")
                }
                .padding(.horizontal, 16)

                Spacer(minLength: 4)

                if !fullScreen {
                    Button(action: onOrbTap) {
                        ZStack {
                            Circle()
                                .fill(RadialGradient(
                                    colors: [
                                        (active ? GemPalette.emerald : GemPalette.cobalt).opacity(0.68),
                                        GemPalette.seafoam.opacity(0.24),
                                        GemPalette.ruby.opacity(0.08),
                                        Color.clear,
                                    ],
                                    center: .center,
                                    startRadius: 16,
                                    endRadius: 116
                                ))
                                .frame(width: 224, height: 224)
                                .scaleEffect(pulse ? 1.07 : 0.94)
                                .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulse)

                            Ellipse()
                                .stroke(
                                    LinearGradient(
                                        colors: [GemPalette.cobalt.opacity(0.75), GemPalette.seafoam.opacity(0.55), GemPalette.ruby.opacity(0.45)],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 2.4
                                )
                                .frame(width: 166, height: 118)
                                .rotationEffect(.degrees(pulse ? 26 : -14))
                                .animation(.easeInOut(duration: 3.4).repeatForever(autoreverses: true), value: pulse)

                            Image("RubySprout")
                                .resizable()
                                .scaledToFit()
                                .frame(width: 64, height: 64)
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Zoe Explore orb. Tap to speak or interrupt.")

                    Text(stateLabel)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.cobalt)
                    Spacer(minLength: 4)
                }

                Text(caption)
                    .font(largeCaptions ? .title3.weight(.medium) : .subheadline)
                    .foregroundStyle(fullScreen ? Color.white : GemPalette.ink)
                    .multilineTextAlignment(.center)
                    .lineLimit(largeCaptions ? 5 : 3)
                    .padding(12)
                    .frame(maxWidth: .infinity)
                    .background(fullScreen ? AnyShapeStyle(.ultraThinMaterial) : AnyShapeStyle(Color.clear))
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .padding(.horizontal, 16)

                if a11yProfile == .deafHoH {
                    HStack(spacing: 8) {
                        TextField("Type to Zoe…", text: $typedMessage)
                            .textFieldStyle(.roundedBorder)
                        Button("Send") {
                            let q = typedMessage.trimmingCharacters(in: .whitespacesAndNewlines)
                            guard !q.isEmpty else { return }
                            typedMessage = ""
                            caption = "You: \(q)\n\n\(brain.respond(q).reply)"
                        }
                        .buttonStyle(GemPrimaryButtonStyle())
                    }
                    .padding(.horizontal, 16)
                }

                // Minimal 3-Button Bottom Dock
                HStack(spacing: 8) {
                    Button(arModeOn ? "● AR" : "✦ AR") {
                        if arModeOn {
                            arModeOn = false
                        } else {
                            cameraOn = false
                            camera.stop()
                            arModeOn = true
                            if a11yProfile != .deafHoH { onOrbTap() }
                        }
                    }
                    .buttonStyle(GemKeycapButtonStyle(accent: arModeOn ? GemPalette.cobalt : GemPalette.seafoam))

                    Button(active ? "Listening…" : (a11yProfile == .deafHoH && fullScreen ? "Look" : "Talk")) {
                        if a11yProfile == .deafHoH && fullScreen {
                            camera.inspect()
                            caption = camera.narration
                        } else {
                            onOrbTap()
                        }
                    }
                    .buttonStyle(GemPrimaryButtonStyle())

                    Button("End", action: stopLive)
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
        }
        .sheet(isPresented: $showToolsSheet) {
            NavigationStack {
                Form {
                    Section("Accessibility & Guided Navigation") {
                        Picker("Mode", selection: $a11yProfile) {
                            Text("Standard").tag(ArExploreCore.AccessibilityProfile.standard)
                            Text("Deaf / Hard-of-Hearing").tag(ArExploreCore.AccessibilityProfile.deafHoH)
                            Text("Blind / Low-Vision Audio").tag(ArExploreCore.AccessibilityProfile.blindLowVision)
                        }
                        Toggle("Kid-Friendly Simple Mode", isOn: $kidMode)
                    }
                    Section("Camera & Spatial AR") {
                        Toggle("Live Camera", isOn: Binding(
                            get: { cameraOn },
                            set: { on in
                                cameraOn = on
                                if on { camera.start() } else { camera.stop() }
                            }
                        ))
                        Toggle("Auto-Glide", isOn: $arRoamOn)
                    }
                    Section("Voice & Fun") {
                        Toggle("Hi Zoe Wake Mode", isOn: $hiZoeMode)
                        Toggle("Zoe 44.1 kHz Offline Voice", isOn: $useNativeVoice)
                        Button("Calm Fact") {
                            showToolsSheet = false
                            let reply = brain.respond("Tell me a short calming science fact about nature.").reply
                            caption = reply
                            if a11yProfile != .deafHoH { speakClean(reply) }
                        }
                        Button("Sing Zoe") {
                            showToolsSheet = false
                            nativeVoice.singZoe()
                        }
                    }
                }
                .navigationTitle("Explore Tools")
                .toolbar {
                    Button("Done") { showToolsSheet = false }
                }
            }
            .presentationDetents([.medium, .large])
        }
        .gemScreen()
        .onAppear {
            pulse = true
            speech.onPartialTranscript = { partial in
                if active && !hiZoeMode && !partial.isEmpty {
                    caption = "You: \(partial)"
                }
            }
            speech.onSilenceTimeout = {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) {
                        if active { speech.start() }
                    }
                }
            }
            speech.onTranscript = { heard in
                guard active else { return }
                if ConversationResponse.isStop(heard) {
                    stopLive()
                    return
                }
                if hiZoeMode {
                    if ZoeSignalAndWakeCore.isHiZoeTrigger(heard) {
                        hiZoeMode = false
                        let trailing = ZoeSignalAndWakeCore.stripWakePrefix(heard)
                        let reply = trailing.isEmpty
                            ? "Hi! I'm Zoe — ready to hang out and explore. What are we getting into?"
                            : brain.respond(trailing).reply
                        caption = reply
                        speakClean(reply)
                    } else if active {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                            if active { speech.start() }
                        }
                    }
                    return
                }
                if cameraOn {
                    camera.inspect()
                }
                let sightPrefix = cameraOn && !camera.narration.isEmpty ? "\(camera.narration) " : ""
                let reply = sightPrefix + brain.respond(heard).reply
                caption = "You: \(heard)\n\n\(reply)"
                speakClean(reply)
            }
            speaker.onFinish = {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.26) {
                        if active { speech.start() }
                    }
                }
            }
        }
        .onDisappear(perform: stopLive)
    }

    private func speakClean(_ raw: String) {
        let clean = ZoeSignalAndWakeCore.sanitizeForSpeech(raw)
        stateLabel = "ZOE IS SPEAKING · TAP ORB TO INTERRUPT"
        if useNativeVoice {
            nativeVoice.speak(clean) {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.26) {
                        if active { speech.start() }
                    }
                }
            }
        } else {
            speaker.speak(clean)
        }
    }

    private func onOrbTap() {
        speaker.stop()
        nativeVoice.stop()
        active = true
        stateLabel = arModeOn ? "AR SPACE LIVE · EXPLORE & TALK" : (cameraOn ? "LIVE VOICE + SIGHT · SPEAK NATURALLY" : "LIVE · LISTENING NATURALLY")
        speech.start()
    }

    private func stopLive() {
        active = false
        hiZoeMode = false
        cameraOn = false
        arModeOn = false
        speech.stop()
        speaker.stop()
        nativeVoice.stop()
        camera.stop()
        stateLabel = "EXPLORE PAUSED · MIC & CAMERA OFF"
    }
}

/// Native Apple ARKit 6DoF + SceneKit Floating 3D GEM Companion View.
struct ZoeArKitSpaceView: UIViewRepresentable {
    @Binding var roamEnabled: Bool
    @Binding var statusText: String
    var onSpotTapped: (ArExploreCore.SpatialDiscovery) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.delegate = context.coordinator
        view.automaticallyUpdatesLighting = true

        // Build Zoe's glowing 3D GEM Prism + Halo Ring node
        let pyramidTop = SCNPyramid(width: 0.12, height: 0.12, length: 0.12)
        pyramidTop.firstMaterial?.diffuse.contents = UIColor(red: 0.38, green: 0.68, blue: 1.0, alpha: 0.88)
        pyramidTop.firstMaterial?.emission.contents = UIColor(red: 0.22, green: 0.52, blue: 0.96, alpha: 0.45)
        let topNode = SCNNode(geometry: pyramidTop)

        let ring = SCNTorus(ringRadius: 0.14, pipeRadius: 0.004)
        ring.firstMaterial?.diffuse.contents = UIColor(red: 0.42, green: 0.90, blue: 0.80, alpha: 0.85)
        let ringNode = SCNNode(geometry: ring)
        ringNode.eulerAngles.x = .pi / 5

        let zoeRoot = SCNNode()
        zoeRoot.position = SCNVector3(0, -0.05, -1.1)
        zoeRoot.addChildNode(topNode)
        zoeRoot.addChildNode(ringNode)
        zoeRoot.runAction(.repeatForever(.rotateBy(x: 0, y: .pi * 2, z: 0, duration: 9.0)))
        view.scene.rootNode.addChildNode(zoeRoot)
        context.coordinator.zoeNode = zoeRoot

        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleTap(_:)))
        view.addGestureRecognizer(tap)

        let cfg = ARWorldTrackingConfiguration()
        cfg.planeDetection = [.horizontal, .vertical]
        view.session.run(cfg)
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {
        context.coordinator.parent = self
    }

    static func dismantleUIView(_ uiView: ARSCNView, coordinator: Coordinator) {
        uiView.session.pause()
    }

    final class Coordinator: NSObject, ARSCNViewDelegate {
        var parent: ZoeArKitSpaceView
        weak var zoeNode: SCNNode?
        private var planeCount = 0

        init(parent: ZoeArKitSpaceView) {
            self.parent = parent
        }

        func renderer(_ renderer: SCNSceneRenderer, didAdd node: SCNNode, for anchor: ARAnchor) {
            guard anchor is ARPlaneAnchor else { return }
            planeCount += 1
            let count = planeCount
            DispatchQueue.main.async {
                self.parent.statusText = "● ARKit 6DoF · \(count) surfaces"
            }
        }

        @objc func handleTap(_ gesture: UITapGestureRecognizer) {
            guard let view = gesture.view as? ARSCNView else { return }
            let pt = gesture.location(in: view)
            guard let query = view.raycastQuery(from: pt, allowing: .estimatedPlane, alignment: .any),
                  let hit = view.session.raycast(query).first,
                  let zoeNode else { return }
            let t = hit.worldTransform.columns.3
            let dest = SCNVector3(t.x, t.y + ArExploreCore.hoverClearanceM, t.z)
            zoeNode.runAction(SCNAction.move(to: dest, duration: 0.85))
            let dist = sqrt(t.x * t.x + t.y * t.y + t.z * t.z)
            let disc = ArExploreCore.SpatialDiscovery(
                primaryLabel: "surface",
                ocrSnippet: "",
                position: ArExploreCore.Vec3(x: t.x, y: t.y, z: t.z),
                distanceMeters: dist
            )
            parent.onSpotTapped(disc)
        }
    }
}
