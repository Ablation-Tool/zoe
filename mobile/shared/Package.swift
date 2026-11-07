// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "ZoeCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "ZoeCore", targets: ["ZoeCore"])],
    targets: [
        .target(name: "ZoeCore", path: "Sources/ZoeCore"),
        .testTarget(name: "ZoeCoreTests", dependencies: ["ZoeCore"], path: "Tests/ZoeCoreTests")
    ]
)
