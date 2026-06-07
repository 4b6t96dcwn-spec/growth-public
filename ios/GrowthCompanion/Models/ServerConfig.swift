import Foundation

struct ServerConfig: Codable, Equatable {
    var host: String
    var apiPort: Int
    var useHTTPS: Bool

    static let storageKey = "growth.server.config"

    static var `default`: ServerConfig {
        ServerConfig(host: "", apiPort: 21323, useHTTPS: true)
    }

    var baseURL: URL? {
        guard !host.isEmpty else { return nil }
        let scheme = useHTTPS ? "https" : "http"
        return URL(string: "\(scheme)://\(host):\(apiPort)/api/v1")
    }

    static func load() -> ServerConfig {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let cfg = try? JSONDecoder().decode(ServerConfig.self, from: data) else {
            return .default
        }
        return cfg
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }
}