import AVFoundation
import SwiftUI
import Vision

final class CameraController: NSObject, ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var isBusy = false
    @Published private(set) var status = "Camera and microphone are idle. No frame has been captured."
    @Published private(set) var recognizedText = ""
    @Published private(set) var labels: [String] = []

    let session = AVCaptureSession()
    private let photoOutput = AVCapturePhotoOutput()
    private let sessionQueue = DispatchQueue(label: "research.zoetic.zoe.camera")
    private let analysisQueue = DispatchQueue(label: "research.zoetic.zoe.vision")
    private var configured = false
    private var pendingInspection = false

    var shareText: String {
        "TEXT\n\(recognizedText.isEmpty ? "No text recognized." : recognizedText)\n\nIMAGE LABELS\n\(labels.isEmpty ? "No labels at or above 50% confidence." : labels.joined(separator: " · "))\n\nModel outputs remain separate. Confidence is not correctness. No image was saved by Zoe."
    }

    var narration: String {
        if !recognizedText.isEmpty { return "Text found. \(recognizedText)" }
        if !labels.isEmpty { return "Image labels. \(labels.joined(separator: ", "))" }
        return "No observation yet. Start the camera, then inspect one frame."
    }

    func start() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            sessionQueue.async { self.configureAndStart() }
        case .notDetermined:
            status = "Requesting camera permission…"
            AVCaptureDevice.requestAccess(for: .video) { granted in
                if granted {
                    self.sessionQueue.async { self.configureAndStart() }
                } else {
                    self.publishStatus("Camera permission was not granted. No camera was opened.")
                }
            }
        default:
            publishStatus("Camera access is denied or restricted. Enable it in Settings to use Guided Vision.")
        }
    }

    private func configureAndStart() {
        if isRunning {
            publishStatus("Camera is already active. Choose Inspect once when ready.")
            return
        }
        if !configured {
            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: device) else {
                publishStatus("No compatible back camera is available.")
                return
            }
            session.beginConfiguration()
            session.sessionPreset = .photo
            defer { session.commitConfiguration() }
            guard session.canAddInput(input), session.canAddOutput(photoOutput) else {
                publishStatus("The camera cannot provide a compatible capture pipeline.")
                return
            }
            session.addInput(input)
            session.addOutput(photoOutput)
            configured = true
        }
        session.startRunning()
        DispatchQueue.main.async {
            self.isRunning = true
            self.status = "Camera active. No continuous analysis. Choose Inspect once."
            if self.pendingInspection {
                self.pendingInspection = false
                self.inspect()
            }
        }
    }

    func inspect() {
        if !isRunning {
            pendingInspection = true
            start()
            return
        }
        guard !isBusy else { return }
        isBusy = true
        status = "Inspecting one frame with on-device OCR and image labels…"
        photoOutput.capturePhoto(with: AVCapturePhotoSettings(), delegate: self)
    }

    func stop() {
        pendingInspection = false
        sessionQueue.async {
            if self.isRunning {
                self.session.stopRunning()
            }
            DispatchQueue.main.async {
                self.isRunning = false
                self.isBusy = false
            }
        }
    }

    private func publishStatus(_ message: String) {
        DispatchQueue.main.async {
            self.pendingInspection = false
            self.status = message
            self.isBusy = false
        }
    }

    private func publish(text: String, labels: [String], errors: [String]) {
        DispatchQueue.main.async {
            self.recognizedText = text
            self.labels = labels
            self.isBusy = false
            self.status = errors.isEmpty
                ? "Inspection complete. Speak, share, or inspect another frame when you choose."
                : "Inspection completed with model errors. Partial results are preserved without claiming success."
        }
    }
}

extension CameraController: AVCapturePhotoCaptureDelegate {
    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        if let error {
            publishStatus("Photo capture failed: \(error.localizedDescription)")
            return
        }
        guard let data = photo.fileDataRepresentation() else {
            publishStatus("The selected frame had no readable image data.")
            return
        }
        analysisQueue.async {
            let textRequest = VNRecognizeTextRequest()
            textRequest.recognitionLevel = .accurate
            textRequest.usesLanguageCorrection = true
            let classifyRequest = VNClassifyImageRequest()
            let handler = VNImageRequestHandler(data: data)
            var recognized = ""
            var labels: [String] = []
            var errors: [String] = []
            do {
                try handler.perform([textRequest])
                recognized = (textRequest.results ?? [])
                    .compactMap { $0.topCandidates(1).first?.string }
                    .joined(separator: "\n")
            } catch {
                errors.append(error.localizedDescription)
            }
            do {
                try handler.perform([classifyRequest])
                labels = (classifyRequest.results ?? [])
                    .filter { $0.confidence >= 0.5 }
                    .sorted { $0.confidence > $1.confidence }
                    .prefix(5)
                    .map { "\($0.identifier) \(Int(($0.confidence * 100).rounded()))%" }
            } catch {
                errors.append(error.localizedDescription)
            }
            if recognized.count > 4000 {
                recognized = String(recognized.prefix(4000)) + "…"
            }
            self.publish(text: recognized, labels: labels, errors: errors)
        }
    }
}
