# growth — Plant Digital Twin

**Repository:** [github.com/fpheromones/growth](https://github.com/fpheromones/growth)

Standalone Mac application for plant tracking, with a REST API for an iPhone companion.

## Quick start (independent app)

```bash
cd ~/Projects/growth
chmod +x run.sh
./run.sh
```

First run installs a local `.venv` automatically. Then opens:

- **UI** (Mac browser or iPhone Safari): `https://localhost:21322` or `https://<mac-ip>:21322`
- **API** (companion apps): `https://<mac-ip>:21323/api/v1/health` (21323 when UI+API run together)

### Commands

```bash
python3 main.py install        # venv + dependencies
python3 main.py start          # UI + API together
python3 main.py serve          # Streamlit only
python3 main.py api            # REST API only
python3 main.py report         # CLI status report
python3 main.py instructions   # Generate care instructions
```

## iPhone companion

See **[docs/IPHONE_COMPANION.md](docs/IPHONE_COMPANION.md)** for the full SwiftUI development roadmap.

Native app: open `ios/GrowthCompanion.xcodeproj` in Xcode.

Short path: run `./run.sh --https` on Mac, open `https://<mac-ip>:21322` in iPhone Safari, or build the iOS app against `https://<mac-ip>:21323/api/v1`.

## Project layout

```
growth/
├── main.py              # Application entry point
├── api.py               # REST API for iPhone
├── app.py               # Streamlit UI
├── run.sh               # One-command Mac launcher
├── config.json          # Plant + server settings
├── growth_log.json      # Measurement history
├── media_database.json  # Photo/video index
├── data/                # Plant context + care actions
├── photos/ videos/      # Media storage
├── scripts/             # CLI utilities
├── docs/                # Companion app guide
└── ios/                 # GrowthCompanion (SwiftUI iPhone app)
```

## Configuration

`config.json` keys:

- `ui_port` / `api_port` — server ports (default 21322; API uses 21323 when both run)
- `mirror_artifacts` — optional sandbox mirror (default `false`)
- `GROWTH_PROJECT_DIR` env var — override project root for portability

## Features

- Photos + videos (≤25 s), EXIF metadata, thumbnails, 3D frame extraction
- Sun/shadow analysis (astral) on rapid multi-photo sessions
- Goal-aware care instructions from `data/plant_context.json`
- Pest/damage analysis hooks (OpenCV heuristics; YOLO-ready)