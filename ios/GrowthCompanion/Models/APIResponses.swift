import Foundation

struct HealthResponse: Codable {
    let status: String
    let projectRoot: String?

    enum CodingKeys: String, CodingKey {
        case status
        case projectRoot = "project_root"
    }
}

struct ServerInfoResponse: Codable {
    let lanIp: String
    let apiPort: Int
    let uiPort: Int
    let apiBase: String?
    let httpsRecommended: Bool?

    enum CodingKeys: String, CodingKey {
        case lanIp = "lan_ip"
        case apiPort = "api_port"
        case uiPort = "ui_port"
        case apiBase = "api_base"
        case httpsRecommended = "https_recommended"
    }
}

struct StatusResponse: Codable {
    let plantName: String?
    let species: String?
    let location: String?
    let latestEntry: GrowthEntry?
    let mediaCount: Int
    let goals: [String]

    enum CodingKeys: String, CodingKey {
        case plantName = "plant_name"
        case species, location
        case latestEntry = "latest_entry"
        case mediaCount = "media_count"
        case goals
    }
}

struct GrowthEntry: Codable {
    let date: String
    let heightCm: Double?
    let widthCm: Double?
    let leanDirection: String?
    let notes: String?
    let actionsTaken: [String]?

    enum CodingKeys: String, CodingKey {
        case date
        case heightCm = "height_cm"
        case widthCm = "width_cm"
        case leanDirection = "lean_direction"
        case notes
        case actionsTaken = "actions_taken"
    }
}

struct InstructionsResponse: Codable {
    let date: String
    let markdown: String
}

struct MediaListResponse: Codable {
    let items: [MediaItem]
    let count: Int
}

struct MediaItem: Codable, Identifiable {
    var id: String { "\(mediaDate)-\(filename)" }
    let filename: String
    let mediaType: String
    let mediaDate: String
    let durationSeconds: Double?
    let source: String?
    let notes: String?
    let thumbnailUrl: String?

    enum CodingKeys: String, CodingKey {
        case filename
        case mediaType = "media_type"
        case mediaDate = "media_date"
        case durationSeconds = "duration_seconds"
        case source, notes
        case thumbnailUrl = "thumbnail_url"
    }
}

struct UploadResult: Codable {
    let added: [MediaItem]
    let rejected: [[String: String]]
    let addedCount: Int

    enum CodingKeys: String, CodingKey {
        case added, rejected
        case addedCount = "added_count"
    }
}