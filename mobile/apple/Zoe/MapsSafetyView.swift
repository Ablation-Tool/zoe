import AVFoundation
import CoreLocation
import MapKit
import SwiftUI
import UIKit

/// Native Apple Location & Compass manager — starts strictly idle until the user taps
/// "Locate once" or toggles "Live location: on", and stops automatically on leave.
final class ZoeLocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let geocoder = CLGeocoder()

    @Published var status = "Location is idle. No location request is active."
    @Published var liveTracking = false
    @Published var latest: CLLocation?
    @Published var firstPoint: CLLocation?
    @Published var headingDegrees: Double?
    @Published var addressLine = ""
    @Published var cameraPosition: MapCameraPosition = .automatic

    private var pendingOneShot = false
    private var lastGeocodeTime: Date = .distantPast

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
    }

    func locateOnce() {
        liveTracking = false
        pendingOneShot = true
        guard ensureAuthorization() else { return }
        status = "Requesting one location from Apple CoreLocation…"
        manager.requestLocation()
    }

    func toggleLive() {
        if liveTracking {
            stopLiveOnly()
            status = "Live location paused. No tracking is active."
            return
        }
        pendingOneShot = false
        liveTracking = true
        guard ensureAuthorization() else { return }
        status = "Live location active (stops automatically when you leave)."
        manager.startUpdatingLocation()
        if CLLocationManager.headingAvailable() {
            manager.startUpdatingHeading()
        }
    }

    func markFirstPoint() {
        guard let latest else {
            status = "Locate once before marking a point."
            return
        }
        firstPoint = latest
        status = "First point marked in memory. Move, then locate again."
    }

    func stopAndClear() {
        pendingOneShot = false
        stopLiveOnly()
        latest = nil
        firstPoint = nil
        headingDegrees = nil
        addressLine = ""
        cameraPosition = .automatic
        status = "Location stopped. No points are retained and no location request is active."
    }

    func pauseOnLeave() {
        let wasActive = liveTracking || pendingOneShot
        pendingOneShot = false
        stopLiveOnly()
        if wasActive {
            status = "Location paused when leaving screen. No tracking is active."
        }
    }

    private func stopLiveOnly() {
        liveTracking = false
        manager.stopUpdatingLocation()
        manager.stopUpdatingHeading()
        geocoder.cancelGeocode()
    }

    private func ensureAuthorization() -> Bool {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            return true
        case .notDetermined:
            status = "Requesting When-In-Use location permission…"
            manager.requestWhenInUseAuthorization()
            return false
        default:
            liveTracking = false
            pendingOneShot = false
            status = "Location permission is off. Enable When-In-Use access in iOS Settings to read GPS."
            return false
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .authorizedWhenInUse || manager.authorizationStatus == .authorizedAlways {
            if liveTracking {
                status = "Live location active (stops automatically when you leave)."
                manager.startUpdatingLocation()
                if CLLocationManager.headingAvailable() {
                    manager.startUpdatingHeading()
                }
            } else if pendingOneShot {
                status = "Requesting one location from Apple CoreLocation…"
                manager.requestLocation()
            }
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        pendingOneShot = false
        latest = loc
        cameraPosition = .region(MKCoordinateRegion(
            center: loc.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.008, longitudeDelta: 0.008)
        ))
        status = liveTracking
            ? "Live location active (CoreLocation · stops on exit)."
            : "Location updated once. No tracking is active."

        if Date().timeIntervalSince(lastGeocodeTime) > 8 {
            lastGeocodeTime = Date()
            geocoder.cancelGeocode()
            geocoder.reverseGeocodeLocation(loc) { [weak self] placemarks, _ in
                guard let self, let p = placemarks?.first else { return }
                let parts = [p.name, p.locality, p.administrativeArea].compactMap { $0 }
                DispatchQueue.main.async {
                    self.addressLine = parts.joined(separator: ", ")
                }
            }
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        if newHeading.headingAccuracy >= 0 {
            headingDegrees = newHeading.trueHeading >= 0 ? newHeading.trueHeading : newHeading.magneticHeading
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        pendingOneShot = false
        status = "Location unavailable: \(error.localizedDescription)"
    }
}

/// Native iOS / iPadOS Maps & Safety Zapp:
///   - Embedded native Apple MapKit viewport (zero API key, zero tracking SDK)
///   - Opt-in One-Shot & Live CoreLocation + Compass + CLGeocoder street address
///   - One-tap handoff to BOTH Apple Maps AND Google Maps
///   - Hardware Flashlight, SafeConvert jump, Share Live Pin & honest Medical ID / Emergency SOS guidance
struct MapsSafetyView: View {
    var onOpenSafeConvert: () -> Void = {}
    @StateObject private var loc = ZoeLocationManager()
    @State private var query = ""
    @State private var torchOn = false
    @State private var toolNotice = ""
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(loc.status)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(GemPalette.cobalt)

                // Native Apple MapKit Live Canvas (shown when a fix is available)
                if let current = loc.latest {
                    Map(position: $loc.cameraPosition) {
                        Marker("You (Zoe Pin)", coordinate: current.coordinate)
                            .tint(GemPalette.ruby)
                        if let first = loc.firstPoint {
                            Marker("Point 1", coordinate: first.coordinate)
                                .tint(GemPalette.emerald)
                        }
                    }
                    .frame(height: 210)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .accessibilityLabel("Native Apple Map showing your current location pin")
                }

                // CoreLocation Controls
                HStack(spacing: 10) {
                    Button("Locate once") { loc.locateOnce() }
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button(loc.liveTracking ? "Live: On" : "Live: Off") { loc.toggleLive() }
                        .buttonStyle(GemKeycapButtonStyle(accent: loc.liveTracking ? GemPalette.emerald : GemPalette.cobalt))
                }

                HStack(spacing: 10) {
                    Button("Mark point 1") { loc.markFirstPoint() }
                        .buttonStyle(GemKeycapButtonStyle())
                    Button("Stop & clear") { loc.stopAndClear() }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
                }

                // Telemetry Readout Card
                VStack(alignment: .leading, spacing: 6) {
                    Text("ON-DEVICE GPS & COMPASS TELEMETRY")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.muted)
                    Text(telemetryText)
                        .font(.subheadline)
                        .foregroundStyle(GemPalette.ink)
                        .textSelection(.enabled)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(16)
                .gemCard(radius: 22)

                // Dual Maps Handoff (Apple Maps + Google Maps)
                VStack(alignment: .leading, spacing: 10) {
                    Text("APPLE MAPS & GOOGLE MAPS")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.muted)
                    TextField("Destination or place (e.g. hospital nearby)…", text: $query)
                        .textFieldStyle(.plain)
                        .padding(12)
                        .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(GemPalette.surfaceHigh))

                    HStack(spacing: 10) {
                        Button("Apple Maps") { openAppleMaps() }
                            .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.cobalt))
                        Button("Google Maps") { openGoogleMaps() }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.emerald))
                    }

                    if let current = loc.latest {
                        let shareText = OsToolsBridge.formatShareLocationMessage(
                            lat: current.coordinate.latitude,
                            lon: current.coordinate.longitude,
                            accuracyMeters: current.horizontalAccuracy,
                            address: loc.addressLine
                        )
                        ShareLink(item: shareText) {
                            Label("Share live map pin", systemImage: "square.and.arrow.up")
                        }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.seafoam))
                    }
                }
                .padding(16)
                .gemCard(radius: 22)

                // Built-In Phone Safety & Tools
                VStack(alignment: .leading, spacing: 10) {
                    Text("BUILT-IN SAFETY & PHONE TOOLS")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(GemPalette.muted)

                    HStack(spacing: 10) {
                        Button(torchOn ? "Flashlight: On" : "Flashlight: Off") { toggleTorch() }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ochre))
                        Button("SafeConvert") { onOpenSafeConvert() }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
                    }

                    HStack(spacing: 10) {
                        Button("Health / Medical ID") {
                            if let url = URL(string: "x-apple-health://") {
                                openURL(url)
                            }
                        }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
                        Button("Call 911 (Dialer)") {
                            if let url = URL(string: "tel://911") {
                                openURL(url)
                            }
                        }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
                    }

                    if !toolNotice.isEmpty {
                        Text(toolNotice)
                            .font(.footnote)
                            .foregroundStyle(GemPalette.ochre)
                    }

                    Text("Apple Emergency SOS: hold Side Button + either Volume button. Zoe never shares your location or dials without your explicit tap, and stops GPS automatically when you leave this screen.")
                        .font(.footnote)
                        .foregroundStyle(GemPalette.muted)
                }
                .padding(16)
                .gemCard(radius: 22)
            }
            .padding(18)
        }
        .gemScreen()
        .onDisappear {
            loc.pauseOnLeave()
            setTorch(false)
        }
    }

    private var telemetryText: String {
        guard let c = loc.latest else {
            return "No location read yet. Tap Locate once or Live: Off to read on-device CoreLocation telemetry."
        }
        var lines: [String] = []
        if !loc.addressLine.isEmpty {
            lines.append("Address (Apple Geocoder): \(loc.addressLine)")
        }
        lines.append(String(format: "Latitude: %.6f · Longitude: %.6f", c.coordinate.latitude, c.coordinate.longitude))
        lines.append(String(format: "Accuracy: +/- %.1f m · Altitude: %.1f m", c.horizontalAccuracy, c.altitude))
        if c.speed >= 0 {
            let kmh = c.speed * 3.6
            let mph = c.speed * 2.23694
            lines.append(String(format: "Speed: %.1f km/h (%.1f mph)", kmh, mph))
        }
        if let heading = loc.headingDegrees {
            lines.append(String(format: "Compass: %.0f° (%@)", heading, OsToolsBridge.compassCardinal(heading)))
        }
        if let first = loc.firstPoint {
            let dist = c.distance(from: first)
            lines.append(String(format: "Straight-line from Point 1: %.1f m", dist))
        }
        return lines.joined(separator: "\n")
    }

    private func openAppleMaps() {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        let urlString: String
        if !q.isEmpty {
            urlString = OsToolsBridge.appleMapsNavigationUrl(destination: q)
        } else if let c = loc.latest {
            urlString = OsToolsBridge.appleMapsPinUrl(lat: c.coordinate.latitude, lon: c.coordinate.longitude, label: "Zoe Pin")
        } else {
            urlString = "https://maps.apple.com/"
        }
        if let url = URL(string: urlString) { openURL(url) }
    }

    private func openGoogleMaps() {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if !q.isEmpty {
            if let appUrl = URL(string: OsToolsBridge.googleMapsAppNavigationUrl(destination: q)),
               UIApplication.shared.canOpenURL(appUrl) {
                openURL(appUrl)
                return
            }
            if let webUrl = URL(string: OsToolsBridge.googleMapsWebDirectionsUrl(destination: q)) {
                openURL(webUrl)
            }
        } else if let c = loc.latest {
            if let webUrl = URL(string: OsToolsBridge.googleMapsPinUrl(lat: c.coordinate.latitude, lon: c.coordinate.longitude)) {
                openURL(webUrl)
            }
        } else if let fallback = URL(string: "https://www.google.com/maps") {
            openURL(fallback)
        }
    }

    private func toggleTorch() {
        setTorch(!torchOn)
    }

    private func setTorch(_ enable: Bool) {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else {
            torchOn = false
            if enable { toolNotice = "Flashlight hardware is unavailable on this device." }
            return
        }
        do {
            try device.lockForConfiguration()
            device.torchMode = enable ? .on : .off
            device.unlockForConfiguration()
            torchOn = enable
            toolNotice = enable ? "Flashlight on." : "Flashlight off."
        } catch {
            torchOn = false
            toolNotice = "Flashlight could not toggle: \(error.localizedDescription)"
        }
    }
}
