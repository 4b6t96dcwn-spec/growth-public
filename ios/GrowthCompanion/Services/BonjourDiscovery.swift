import Foundation
import Network

@MainActor
final class BonjourDiscovery: ObservableObject {
    @Published var discoveredHost: String?
    @Published var discoveredPort: Int?
    @Published var status: String = "Searching…"

    private var browser: NWBrowser?

    func start() {
        stop()
        let params = NWParameters()
        params.includePeerToPeer = true
        browser = NWBrowser(for: .bonjour(type: "_growth._tcp", domain: nil), using: params)
        browser?.browseResultsChangedHandler = { [weak self] results, _ in
            Task { @MainActor in
                guard let self else { return }
                if let first = results.first,
                   case .service(let name, _, _, _) = first.endpoint {
                    self.status = "Found: \(name)"
                    self.resolve(endpoint: first.endpoint)
                } else {
                    self.status = "No Mac found on network"
                }
            }
        }
        browser?.start(queue: .main)
    }

    func stop() {
        browser?.cancel()
        browser = nil
    }

    private func resolve(endpoint: NWEndpoint) {
        let conn = NWConnection(to: endpoint, using: .tcp)
        conn.stateUpdateHandler = { [weak self] state in
            if case .ready = state {
                if case .hostPort(let host, let port) = conn.endpoint {
                    Task { @MainActor in
                        self?.discoveredHost = "\(host)"
                        self?.discoveredPort = Int(port.rawValue)
                    }
                }
                conn.cancel()
            }
        }
        conn.start(queue: .main)
    }
}