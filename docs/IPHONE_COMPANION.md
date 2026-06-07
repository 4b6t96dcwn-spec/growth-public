# Growth Companion — iPhone App Design

**Repository:** [github.com/fpheromones/growth](https://github.com/fpheromones/growth) (`ios/`)

Native iPhone app for capturing plant media and reading care guidance. The **Mac `growth` app remains authoritative** — all analysis, storage, and instruction generation happen there.

---

## 1. Product vision

**One-line:** Walk the garden with your phone; the Mac remembers everything and tells you what to do next.

**Principles**
- Capture-first: optimized for multi-angle photo walks and short video clips
- Mac does the thinking: size estimates, sun/shadow, pest hooks, instructions
- Works on home Wi-Fi only (no cloud, no account)
- Hand-friendly: large tap targets, one-thumb flows (pins/cast constraint from plant context)
- Honest offline behavior: queue uploads when Mac is unreachable; never pretend analysis ran locally

---

## 2. Architecture

```
┌─────────────────────────────────────┐
│  GrowthCompanion (iOS, SwiftUI)     │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │ Capture │ │Dashboard│ │  Care  │ │
│  └────┬────┘ └────┬────┘ └───┬────┘ │
│       │           │          │      │
│       └───────────┴──────────┘      │
│                   │                 │
│            GrowthAPIClient          │
│         (URLSession + multipart)    │
└───────────────────┬─────────────────┘
                    │ Wi-Fi (HTTP or HTTPS)
                    ▼
┌─────────────────────────────────────┐
│  Mac — ~/Projects/growth            │
│  ./run.sh --https                   │
│  ├── Streamlit UI     :ui_port      │
│  ├── FastAPI          :api_port     │
│  ├── photos/ videos/ models_3d/   │
│  └── JSON DB + plant_context       │
└─────────────────────────────────────┘
```

**Stack**
| Layer | Choice |
|-------|--------|
| UI | SwiftUI (iOS 17+) |
| State | `@Observable` view models (MVVM) |
| Networking | `URLSession`, async/await |
| Camera | `AVFoundation` + `PhotosUI` |
| Persistence | `UserDefaults` (server config), `FileManager` (upload queue) |
| Discovery (v2) | Network.framework Bonjour |

---

## 3. Users & primary jobs

| Job | When | App response |
|-----|------|--------------|
| **360° session** | Weekly, morning | Guided clockwise walk, 12+ shots, auto-upload batch |
| **Quick snap** | After pruning / pest spot | 1–3 photos + optional note |
| **Check status** | Anytime | Height, lean, last session date |
| **Read care plan** | Before gardening | This week's pinch / feed / water tasks |
| **Log action** | After pinching | "Tip-pinched 3 eastern stems" → Mac log |

---

## 4. Screen map

```
TabView
├── Home (Dashboard)
│   ├── Plant summary card (height, width, lean)
│   ├── Connection status (Mac reachable?)
│   ├── Goals chips
│   └── "Start capture session" CTA
│
├── Capture
│   ├── Session type picker
│   │   ├── 360° Walk (guided)
│   │   ├── Overhead + base set
│   │   └── Quick photo / video
│   ├── Camera / library
│   ├── Session progress (shot 4 of 12)
│   └── Upload review → Send to Mac
│
├── Care
│   ├── Instructions (markdown)
│   ├── Pruning priorities (from context)
│   └── Log action sheet
│
├── History
│   ├── Sessions by date
│   └── Media grid (thumbnails from API)
│
└── Settings
    ├── Mac host + API port + HTTPS toggle
    ├── Test connection
    ├── Trust self-signed cert hint
    └── Photo protocol reference
```

**Modal flows**
- First launch: Connect to Mac wizard (enter IP, test `/health`)
- Upload result: added / rejected list (esp. video >25s)
- Connection lost: offline queue banner

---

## 5. Core user flows

### 5.1 First connect

1. User runs `./run.sh --https` on Mac
2. iPhone → Settings tab → Host `192.168.0.228`, Port `21323` (API), HTTPS on
3. Tap **Test connection** → `GET /api/v1/health`
4. If cert warning in app: show "Safari trusts after Show Details; native app uses ATS local networking + optional cert bypass for self-signed"
5. Save to `UserDefaults`

### 5.2 Guided 360° capture (signature flow)

Matches `data/plant_context.json` photo protocol:

1. User taps **Start 360° session**
2. App shows: "Hold phone at face level. Walk clockwise."
3. CoreMotion compass → arrow hints next bearing (12 stops ≈ 30° each)
4. At each stop: capture photo (camera) or tap "Skip"
5. Final 3 prompts: "Shoot top foliage from above"
6. Review strip of thumbnails
7. Add optional note → **Upload all** → `POST /api/v1/media/upload`
8. Success → "Mac received 12 items. Open Dashboard on Mac for sun analysis."

### 5.3 Quick video (≤25s)

1. User records in-app or picks from library
2. `AVAsset.duration` check **before** upload
3. If >25s: alert with trim instructions
4. Upload → show thumbnail in result (from API response `thumbnail_path` is Mac-local; need thumbnail endpoint — see §7)

### 5.4 Morning care check

1. Open **Care** tab → fetch `/api/v1/instructions`
2. Render markdown (use `Text` + attributed string or lightweight MarkdownUI package)
3. Pinch tasks shown as checklist (local only until `POST /growth` exists)

---

## 6. Swift data models (match API)

```swift
struct ServerConfig: Codable {
    var host: String          // "192.168.0.228"
    var apiPort: Int          // 21323 (21322 when API-only)
    var useHTTPS: Bool        // true recommended
}

struct StatusResponse: Codable {
    let plantName: String?
    let species: String?
    let location: String?
    let latestEntry: GrowthEntry?
    let mediaCount: Int
    let goals: [String]
}

struct GrowthEntry: Codable {
    let date: String
    let heightCm: Double?
    let widthCm: Double?
    let leanDirection: String?
    let notes: String?
    let actionsTaken: [String]?
}

struct MediaItem: Codable {
    let filename: String
    let mediaType: String
    let mediaDate: String
    let durationSeconds: Double?
    let source: String
    let notes: String
}

struct UploadResult: Codable {
    let added: [MediaItem]
    let rejected: [[String: String]]  // filename + reason
    let addedCount: Int
}
```

`GrowthAPIClient` methods:
- `health() async throws -> Bool`
- `status() async throws -> StatusResponse`
- `instructions() async throws -> (date: String, markdown: String)`
- `media(limit:) async throws -> [MediaItem]`
- `context() async throws -> PlantContextBundle`
- `upload(files: [URL], notes: String) async throws -> UploadResult`

---

## 7. API gaps to add on Mac (before / during iOS build)

| Priority | Endpoint | Why |
|----------|----------|-----|
| **P0** | `GET /api/v1/media/{filename}/thumbnail` | ✅ History grid images on iPhone |
| **P0** | `GET /api/v1/server/info` | ✅ Returns LAN IP, ui_port, api_port, https hint |
| **P1** | `POST /api/v1/growth` | Log measurements + actions from iPhone |
| **P1** | `POST /api/v1/growth/actions` | "tip_pinched_eastern" events |
| **P2** | Bonjour advertise `_growth._tcp` | Auto-discover Mac |
| **P2** | `WS /api/v1/events` | Push upload/analysis complete |

Existing endpoints (ready now): `/health`, `/status`, `/instructions`, `/media`, `/context`, `/media/upload`, `/media/{filename}/thumbnail`, `/server/info`.

`GET /api/v1/media` now includes `thumbnail_url` on each item for direct use in SwiftUI `AsyncImage`.

---

## 8. Connection & security

**Lesson from Safari:** iOS **HTTPS-Only** blocks plain `http://` to LAN IPs.

| Approach | iOS app | Effort |
|----------|---------|--------|
| Mac serves HTTPS (`./run.sh --https`) | `URLSession` with self-signed cert delegate | Medium — implement `urlSession(_:didReceive:completionHandler:)` to trust local cert |
| HTTP only | `NSAllowsLocalNetworking` in Info.plist | Easy — but Safari still blocks; native app OK |
| Both | Settings toggle `useHTTPS` | Recommended |

**Info.plist (required)**
- `NSCameraUsageDescription`
- `NSPhotoLibraryUsageDescription`
- `NSMicrophoneUsageDescription` (if video with sound)
- `NSLocalNetworkUsageDescription`
- `NSAppTransportSecurity` → `NSAllowsLocalNetworking` = true

---

## 9. MVP scope (v0.1 — ~2 weeks)

**In**
- Settings + connection test
- Dashboard (`/status`)
- Care instructions (`/instructions`)
- Photo upload from library + camera (multi-select)
- Video upload with 25s guard
- Basic upload result feedback

**Out (v0.2+)**
- Compass-guided 360 walk
- Offline queue
- Thumbnail history grid (blocked on P0 API)
- Widget
- Bonjour
- Action logging to Mac

---

## 10. Xcode project structure

```
GrowthCompanion/
├── GrowthCompanionApp.swift      # @main
├── Models/
│   ├── ServerConfig.swift
│   ├── APIResponses.swift
│   └── CaptureSession.swift
├── Services/
│   ├── GrowthAPIClient.swift
│   ├── UploadQueue.swift         # v0.2
│   └── CertificateTrust.swift    # self-signed HTTPS
├── ViewModels/
│   ├── SettingsViewModel.swift
│   ├── DashboardViewModel.swift
│   ├── CaptureViewModel.swift
│   └── CareViewModel.swift
├── Views/
│   ├── MainTabView.swift
│   ├── DashboardView.swift
│   ├── CaptureView.swift
│   ├── CareView.swift
│   ├── HistoryView.swift
│   └── SettingsView.swift
└── Resources/
    └── Info.plist
```

---

## 11. Build phases

| Phase | Deliverable | Days |
|-------|-------------|------|
| **A** | Xcode project + Settings + `health()` test | 1–2 |
| **B** | Dashboard + Care tabs wired to API | 2–3 |
| **C** | Photo/video upload + 25s validation | 3–4 |
| **D** | Mac API: thumbnail + server/info endpoints | 1 |
| **E** | History grid with thumbnails | 2 |
| **F** | Guided 360° capture with compass | 4–5 |
| **G** | Offline upload queue | 3 |
| **H** | Bonjour discovery | 2 |

---

## 12. Distribution

| Goal | Requirement |
|------|-------------|
| Run on your iPhone (USB) | Free Apple ID in Xcode |
| TestFlight | Apple Developer Program ($99/yr) |
| App Store | Developer Program + review |

---

## 13. Immediate next steps

1. **You:** Create Xcode project `GrowthCompanion` (SwiftUI, iOS 17)
2. **You:** Implement `GrowthAPIClient` + Settings screen; confirm `health()` against `./run.sh --https`
3. **Mac side (Grok Build):** Add thumbnail + `server/info` API endpoints
4. **You:** Build Dashboard + Care tabs
5. **You:** Capture tab with `PhotosPicker` + camera

When ready for Phase A, say **"scaffold the Swift API client"** or **"add thumbnail endpoint to api.py"** and we implement the Mac or iOS side next.
