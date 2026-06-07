import Foundation

@MainActor
final class SettingsViewModel: ObservableObject {
    @Published var host: String
    @Published var apiPort: String
    @Published var useHTTPS: Bool
    @Published var testResult: String?
    @Published var isTesting = false

    private let api = GrowthAPIClient.shared
    private let discovery = BonjourDiscovery()

    init() {
        let cfg = ServerConfig.load()
        host = cfg.host
        apiPort = String(cfg.apiPort)
        useHTTPS = cfg.useHTTPS
    }

    func applyFromDiscovery() {
        if let h = discovery.discoveredHost {
            host = h
        }
        if let p = discovery.discoveredPort {
            apiPort = String(p)
        }
    }

    func startDiscovery() {
        discovery.start()
    }

    var discoveryStatus: String { discovery.status }

    func save() {
        let cfg = ServerConfig(
            host: host.trimmingCharacters(in: .whitespaces),
            apiPort: Int(apiPort) ?? 21323,
            useHTTPS: useHTTPS
        )
        api.saveConfig(cfg)
    }

    func testConnection() async {
        save()
        isTesting = true
        testResult = nil
        defer { isTesting = false }
        do {
            let health = try await api.health()
            let info = try await api.serverInfo()
            testResult = "✅ Connected — \(health.status)\nMac: \(info.lanIp) API:\(info.apiPort)"
        } catch let err {
            testResult = "❌ \(err.localizedDescription)"
        }
    }
}