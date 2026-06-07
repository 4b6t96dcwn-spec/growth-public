# GrowthCompanion — iPhone App

Native companion for the Mac `growth` plant tracker.

**Monorepo:** [github.com/fpheromones/growth](https://github.com/fpheromones/growth) (`ios/`)

## Open in Xcode

```bash
open ~/Projects/growth/ios/GrowthCompanion.xcodeproj
```

## One-time setup (requires your action)

1. Select target **GrowthCompanion** → **Signing & Capabilities**
2. Choose your **Team** (free Apple ID works for your own device)
3. Connect iPhone via USB → select it as run destination → **Run**

## Mac server (must be running)

```bash
cd ~/Projects/growth
./run.sh --https
```

## Settings in app

- Host: your Mac LAN IP (e.g. `192.168.0.228`)
- API Port: `21323`
- HTTPS: on
- Tap **Test Connection**

Or tap **Search for growth Mac** (Bonjour).

## Features

- Dashboard (`/status`)
- Care instructions (`/instructions`)
- Capture: photos, video ≤25s, 360° compass guide
- History with thumbnails
- Offline upload queue
- Bonjour discovery