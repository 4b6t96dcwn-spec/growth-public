import Foundation

enum CaptureSessionType: String, CaseIterable, Identifiable {
    case walk360 = "360° Walk"
    case overheadBase = "Overhead + Base"
    case quick = "Quick Capture"

    var id: String { rawValue }

    var targetShotCount: Int {
        switch self {
        case .walk360: return 12
        case .overheadBase: return 6
        case .quick: return 1
        }
    }

    var instruction: String {
        switch self {
        case .walk360:
            return "Hold phone at face level. Walk clockwise. Tap capture at each arrow."
        case .overheadBase:
            return "Capture base close-ups, then 3 overhead shots."
        case .quick:
            return "One or more quick photos or a short video (≤25s)."
        }
    }
}

struct CapturedAsset: Identifiable {
    let id = UUID()
    let url: URL
    let isVideo: Bool
    let durationSeconds: Double?
}

struct CaptureSession: Identifiable {
    let id = UUID()
    let type: CaptureSessionType
    var assets: [CapturedAsset] = []
    var note: String = ""
    var currentBearingIndex: Int = 0

    var progress: String {
        "\(assets.count) / \(type.targetShotCount) shots"
    }
}