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
    @State private var arStatus = "● ARKit 6DoF · Scanning surfaces…"
    @State private var pulse = false
    @State private var useNativeVoice = false
    @State private var caption = "Hi, I'm Zoe. Tap the orb to talk hands-free, Live + Cam for sight + voice, or ✦ AR Space to let Zoe float and explore your room!"
    @State private var stateLabel = "TAP ORB TO GO LIVE · MIC & CAMERA START OFF"

    var body: some View {
        VStack(spacing: 14) {
            HStack(spacing: 6) {
                Button(arModeOn ? "Camera: AR" : (cameraOn ? "Camera: on" : "Camera: off")) {
                    if arModeOn {
                        arModeOn = false
                        return
                    }
                    cameraOn.toggle()
                    if cameraOn {
                        camera.start()
                    } else {
                        camera.stop()
                    }
                }
                .buttonStyle(GemKeycapButtonStyle(accent: (cameraOn || arModeOn) ? GemPalette.emerald : GemPalette.muted))

                Button(hiZoeMode ? "Hi Zoe: on" : "Hi Zoe: off") {
                    hiZoeMode.toggle()
                    if hiZoeMode {
                        active = true
                        stateLabel = "WAITING FOR 'HI ZOE' · VISIBLE OPT-IN"
                        caption = "\"Hi Zoe\" hangout mode is active. Say \"Hi Zoe\" anytime — tap End / Mute to turn off."
                        speech.start()
                    } else {
                        stopLive()
                    }
                }
                .buttonStyle(GemKeycapButtonStyle(accent: hiZoeMode ? GemPalette.seafoam : GemPalette.muted))

                Button(useNativeVoice ? "Voice: Zoe 44k" : "Voice: iOS") {
                    useNativeVoice.toggle()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: useNativeVoice ? GemPalette.ruby : GemPalette.muted))
            }
            .padding(.horizontal, 16)

            if arModeOn {
                ZStack(alignment: .topLeading) {
                    ZoeArKitSpaceView(roamEnabled: $arRoamOn, statusText: $arStatus) { spotted in
                        let q = ArExploreCore.buildCuriousQuestion(for: spotted)
                        caption = q
                        speakClean(q)
                    }
                    .frame(height: 320)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))

                    HStack {
                        Text(arStatus)
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(.ultraThinMaterial, in: Capsule())
                        Spacer()
                        Button(arRoamOn ? "Roam: on" : "Roam: off") {
                            arRoamOn.toggle()
                        }
                        .font(.caption2.weight(.semibold))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(.ultraThinMaterial, in: Capsule())
                    }
                    .padding(10)
                }
                .padding(.horizontal, 16)
            } else if cameraOn {
                ZStack(alignment: .topTrailing) {
                    CameraPreview(session: camera.session)
                        .frame(height: 210)
                        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    Button("Look now") {
                        camera.inspect()
                        let sight = camera.narration
                        caption = sight
                        speakClean(sight)
                    }
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(10)
                }
                .padding(.horizontal, 16)
            }

            if !arModeOn {
                Spacer(minLength: 4)
                Button(action: onOrbTap) {
                    ZStack {
                        Circle()
                            .fill(RadialGradient(
                                colors: [
                                    (active ? GemPalette.emerald : GemPalette.cobalt).opacity(0.65),
                                    GemPalette.seafoam.opacity(0.18),
                                    Color.clear,
                                ],
                                center: .center,
                                startRadius: 20,
                                endRadius: cameraOn ? 78 : 112
                            ))
                            .frame(width: cameraOn ? 148 : 212, height: cameraOn ? 148 : 212)
                            .scaleEffect(pulse ? 1.07 : 0.94)
                            .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulse)

                        Image("RubySprout")
                            .resizable()
                            .scaledToFit()
                            .frame(width: cameraOn ? 46 : 64, height: cameraOn ? 46 : 64)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Zoe Explore orb. Tap to speak or interrupt.")
            }

            Text(stateLabel)
                .font(.caption.weight(.semibold))
                .foregroundStyle(GemPalette.cobalt)

            Text(caption)
                .font(.body)
                .foregroundStyle(GemPalette.ink)
                .multilineTextAlignment(.center)
                .padding(16)
                .frame(maxWidth: .infinity)
                .gemCard(radius: 22)
                .padding(.horizontal, 16)

            HStack(spacing: 8) {
                Button(arModeOn ? "✦ AR: On" : "✦ AR Space") {
                    if arModeOn {
                        arModeOn = false
                    } else {
                        cameraOn = false
                        camera.stop()
                        arModeOn = true
                        onOrbTap()
                    }
                }
                .buttonStyle(GemKeycapButtonStyle(accent: arModeOn ? GemPalette.cobalt : GemPalette.muted))

                Button("Sing Zoe") {
                    stateLabel = "SINGING ZOE (44.1 kHz OFFLINE)"
                    caption = "Singing Zoe's native soprano melody offline…"
                    nativeVoice.singZoe()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
            }
            .padding(.horizontal, 16)

            Spacer(minLength: 4)

            HStack(spacing: 8) {
                Button(active ? "Listening…" : "Talk Now", action: onOrbTap)
                    .buttonStyle(GemPrimaryButtonStyle())
                Button(arModeOn ? "AR Live" : (cameraOn && active ? "Cam Live" : "Live + Cam")) {
                    arModeOn = false
                    if !cameraOn {
                        cameraOn = true
                        camera.start()
                    }
                    onOrbTap()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.seafoam))
                Button("End / Mute", action: stopLive)
                    .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
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
