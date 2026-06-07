import Foundation
import AVFoundation

@MainActor
final class CaptureViewModel: ObservableObject {
    @Published var sessionType: CaptureSessionType = .quick
    @Published var session = CaptureSession(type: .quick)
    @Published var uploadMessage: String?
    @Published var isUploading = false
    @Published var headingDegrees: Double = 0

    private let maxVideoSeconds = 25.0

    func resetSession() {
        session = CaptureSession(type: sessionType)
    }

    func onTypeChange(_ type: CaptureSessionType) {
        sessionType = type
        resetSession()
    }

    func addAsset(url: URL, isVideo: Bool) async -> String? {
        if isVideo {
            let duration = await videoDuration(url: url)
            if let duration, duration > maxVideoSeconds {
                return String(format: "Video %.1fs exceeds %.0fs limit", duration, maxVideoSeconds)
            }
            session.assets.append(CapturedAsset(url: url, isVideo: true, durationSeconds: duration))
        } else {
            session.assets.append(CapturedAsset(url: url, isVideo: false, durationSeconds: nil))
            if sessionType == .walk360 {
                session.currentBearingIndex = min(session.currentBearingIndex + 1, sessionType.targetShotCount - 1)
            }
        }
        return nil
    }

    func upload() async {
        guard !session.assets.isEmpty else {
            uploadMessage = "No media to upload"
            return
        }
        isUploading = true
        uploadMessage = nil
        defer { isUploading = false }
        let files = session.assets.map(\.url)
        do {
            let result = try await GrowthAPIClient.shared.upload(files: files, notes: session.note)
            uploadMessage = "✅ Uploaded \(result.addedCount). Rejected: \(result.rejected.count)"
            if result.addedCount > 0 { resetSession() }
        } catch {
            UploadQueue.shared.enqueue(files: files, notes: session.note)
            uploadMessage = "⚠️ Offline — queued \(files.count) file(s) for retry"
        }
    }

    func flushQueue() async {
        let r = await UploadQueue.shared.flush()
        uploadMessage = "Queue flush: \(r.sent) sent, \(r.failed) failed"
    }

    private func videoDuration(url: URL) async -> Double? {
        let asset = AVURLAsset(url: url)
        guard let dur = try? await asset.load(.duration) else { return nil }
        return CMTimeGetSeconds(dur)
    }
}