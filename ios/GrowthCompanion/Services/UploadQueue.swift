import Foundation

struct QueuedUpload: Codable, Identifiable {
    let id: UUID
    let filePaths: [String]
    let notes: String
    let createdAt: Date
}

@MainActor
final class UploadQueue: ObservableObject {
    static let shared = UploadQueue()

    @Published private(set) var pending: [QueuedUpload] = []

    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return dir.appendingPathComponent("upload_queue.json")
    }()

    init() { load() }

    func enqueue(files: [URL], notes: String) {
        let item = QueuedUpload(
            id: UUID(),
            filePaths: files.map(\.path),
            notes: notes,
            createdAt: Date()
        )
        pending.append(item)
        save()
    }

    func flush() async -> (sent: Int, failed: Int) {
        var sent = 0, failed = 0
        let client = GrowthAPIClient.shared
        for item in pending {
            let urls = item.filePaths.compactMap { URL(fileURLWithPath: $0) }
            guard !urls.isEmpty else { continue }
            do {
                _ = try await client.upload(files: urls, notes: item.notes)
                sent += 1
                pending.removeAll { $0.id == item.id }
            } catch {
                failed += 1
            }
        }
        save()
        return (sent, failed)
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let items = try? JSONDecoder().decode([QueuedUpload].self, from: data) else { return }
        pending = items
    }

    private func save() {
        if let data = try? JSONEncoder().encode(pending) {
            try? data.write(to: fileURL)
        }
    }
}