import Foundation

@MainActor
final class HistoryViewModel: ObservableObject {
    @Published var items: [MediaItem] = []
    @Published var error: String?
    @Published var isLoading = false

    private let api = GrowthAPIClient.shared

    func refresh() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let resp = try await api.media(limit: 40)
            items = resp.items
        } catch let err {
            error = err.localizedDescription
        }
    }

    func thumbURL(for item: MediaItem) -> URL? {
        api.thumbnailURL(for: item)
    }
}