import Foundation

enum GrowthAPIError: LocalizedError {
    case notConfigured
    case badURL
    case http(Int)
    case decode(Error)

    var errorDescription: String? {
        switch self {
        case .notConfigured: return "Set Mac host in Settings"
        case .badURL: return "Invalid server URL"
        case .http(let code): return "Server returned HTTP \(code)"
        case .decode(let e): return "Decode error: \(e.localizedDescription)"
        }
    }
}

@MainActor
final class GrowthAPIClient: ObservableObject {
    static let shared = GrowthAPIClient()

    @Published var config: ServerConfig = ServerConfig.load()

    private let trustDelegate = CertificateTrustDelegate()
    private lazy var session: URLSession = {
        URLSession(configuration: .default, delegate: trustDelegate, delegateQueue: nil)
    }()

    func saveConfig(_ cfg: ServerConfig) {
        config = cfg
        cfg.save()
    }

    private func url(path: String) throws -> URL {
        guard let base = config.baseURL else { throw GrowthAPIError.notConfigured }
        return base.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let url = try url(path: path)
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse else { throw GrowthAPIError.badURL }
        guard (200...299).contains(http.statusCode) else { throw GrowthAPIError.http(http.statusCode) }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw GrowthAPIError.decode(error)
        }
    }

    func health() async throws -> HealthResponse {
        try await get("health")
    }

    func serverInfo() async throws -> ServerInfoResponse {
        try await get("server/info")
    }

    func status() async throws -> StatusResponse {
        try await get("status")
    }

    func instructions() async throws -> InstructionsResponse {
        try await get("instructions")
    }

    func media(limit: Int = 20) async throws -> MediaListResponse {
        let url = try url(path: "media?limit=\(limit)")
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw GrowthAPIError.http((resp as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return try JSONDecoder().decode(MediaListResponse.self, from: data)
    }

    func thumbnailURL(for item: MediaItem) -> URL? {
        guard let base = config.baseURL?.deletingLastPathComponent().deletingLastPathComponent(),
              let path = item.thumbnailUrl else { return nil }
        return URL(string: path, relativeTo: base.appendingPathComponent("/"))?
            .absoluteURL
    }

    func upload(files: [URL], notes: String) async throws -> UploadResult {
        let endpoint = try url(path: "media/upload")
        let boundary = UUID().uuidString
        var body = Data()

        for file in files {
            let data = try Data(contentsOf: file)
            let name = file.lastPathComponent
            let mime = file.pathExtension.lowercased() == "mov" ? "video/quicktime" : "image/jpeg"
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"\(name)\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
            body.append(data)
            body.append("\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"source\"\r\n\r\niphone\r\n".data(using: .utf8)!)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"notes\"\r\n\r\n\(notes)\r\n".data(using: .utf8)!)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.httpBody = body

        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw GrowthAPIError.http((resp as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return try JSONDecoder().decode(UploadResult.self, from: data)
    }
}