import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var status: StatusResponse?
    @Published var error: String?
    @Published var isLoading = false

    func refresh() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            status = try await GrowthAPIClient.shared.status()
        } catch let err {
            error = err.localizedDescription
        }
    }
}