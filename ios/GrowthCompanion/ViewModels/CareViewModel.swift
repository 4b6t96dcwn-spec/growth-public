import Foundation

@MainActor
final class CareViewModel: ObservableObject {
    @Published var markdown: String = ""
    @Published var date: String = ""
    @Published var error: String?
    @Published var isLoading = false

    func refresh() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let resp = try await GrowthAPIClient.shared.instructions()
            date = resp.date
            markdown = resp.markdown
        } catch let err {
            error = err.localizedDescription
        }
    }
}