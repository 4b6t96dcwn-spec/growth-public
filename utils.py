#!/usr/bin/env python3
"""
utils.py
Shared utilities for the growth project (photos + videos).

Consolidates:
- Project root discovery
- JSON load/save
- Media metadata (EXIF for photos, duration for videos)
- add_media (generalized from add_photo, with 25s video limit)
- Artifacts mirroring

Used by app.py and scripts/* to avoid duplication.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from PIL import Image
from PIL.ExifTags import TAGS

try:
    import cv2  # type: ignore
    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False

# -----------------------------
# Project layout (resolved once)
# -----------------------------
def get_project_root() -> Path:
    """Portable project root discovery.
    Priority:
    1. GROWTH_PROJECT_DIR env var (for other devices / containers / portability)
    2. Walk up from cwd / __file__ looking for config.json + growth_log.json
    3. Fallback to cwd
    Works cross-platform (Windows, Linux, macOS, Raspberry Pi, etc.).
    """
    # 1. Explicit env for portability to other devices
    env_dir = os.environ.get("GROWTH_PROJECT_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        if (p / "config.json").is_file():
            return p

    candidates = [Path.cwd()]
    try:
        if "__file__" in globals():
            here = Path(__file__).resolve().parent
            candidates.extend([here, here.parent, here.parent.parent])
    except Exception:
        pass
    for start in candidates:
        p = start
        for _ in range(8):
            if (p / "config.json").is_file() and (p / "growth_log.json").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent
    return Path.cwd()

ROOT = get_project_root()
MEDIA_DB = ROOT / "media_database.json"
PHOTOS_DIR = ROOT / "photos"
VIDEOS_DIR = ROOT / "videos"
ARTIFACTS_DIR = ROOT / "artifacts" / "growth"

# Supported video extensions (iPhone + common)
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
MAX_VIDEO_SECONDS = 25.0
DEFAULT_PORT = 21322


# -----------------------------
# JSON helpers
# -----------------------------
def load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default if default is not None else []


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# Media metadata
# -----------------------------
def get_exif_datetime(path: Path) -> Optional[datetime]:
    """Return original capture datetime (timezone-aware, America/New_York assumed) or None."""
    try:
        image = Image.open(path)
        exif = image._getexif() or {}
        for tag_id, value in exif.items():
            if TAGS.get(tag_id) == "DateTimeOriginal":
                naive = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo("America/New_York")
                    return naive.replace(tzinfo=tz)
                except Exception:
                    return naive  # fallback naive
    except Exception:
        pass
    return None


def get_video_duration(path: Path) -> Optional[float]:
    """Return duration in seconds using OpenCV, or None if unavailable / unreadable."""
    if not CV2_AVAILABLE:
        return None
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and fps > 0 and frame_count and frame_count > 0:
            return float(frame_count) / float(fps)
    except Exception:
        pass
    return None


def get_video_creation_time(path: Path) -> Optional[datetime]:
    """Robust extraction of video creation time.
    Tries multiple ffprobe tags (creation_time, com.apple.quicktime.creationdate, date, etc.),
    multiple datetime formats, with short timeout. Falls back to mtime.
    Returns aware datetime in America/New_York or None.
    """
    if not path.exists():
        return None

    # Try ffprobe with robustness
    try:
        import subprocess
        import json as _json
        # Try broader tags
        cmd = [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_entries", "format_tags=creation_time,com.apple.quicktime.creationdate,date,creation_date",
            "-show_format", str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            data = _json.loads(result.stdout)
            tags = data.get("format", {}).get("tags", {}) or {}
            ctime = None
            for key in ("creation_time", "com.apple.quicktime.creationdate", "date", "creation_date"):
                if key in tags and tags[key]:
                    ctime = tags[key]
                    break
            if ctime:
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S"):
                    try:
                        if "Z" in ctime or "+" in ctime or "-" in ctime[10:]:
                            dt = datetime.fromisoformat(ctime.replace("Z", "+00:00"))
                        else:
                            dt = datetime.strptime(ctime, fmt)
                        try:
                            import zoneinfo
                            ny = zoneinfo.ZoneInfo("America/New_York")
                            return dt.astimezone(ny) if dt.tzinfo else dt.replace(tzinfo=ny)
                        except Exception:
                            return dt
                    except Exception:
                        continue
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass  # No ffprobe, timeout, or parse fail - silent, normal

    # Robust mtime fallback (creation or mod time)
    try:
        stat = path.stat()
        ts = getattr(stat, "st_birthtime", stat.st_mtime)  # birthtime on some Unix/Mac
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


def get_media_date(path: Path) -> str:
    """Best effort capture date as YYYY-MM-DD.
    For videos: prefers embedded creation_time (ffprobe), falls back to mtime.
    For photos: EXIF first, then mtime.
    """
    mtype = get_media_type(path)
    if mtype == "video":
        dt = get_video_creation_time(path)
        if dt:
            return dt.strftime("%Y-%m-%d")
    else:
        dt = get_exif_datetime(path)
        if dt:
            return dt.strftime("%Y-%m-%d")

    # final fallback
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def get_media_type(path: Path) -> str:
    return "video" if path.suffix.lower() in VIDEO_EXTS else "photo"


def get_media_info(path: Path) -> Dict[str, Any]:
    """Return a small info dict (type, duration if video, date, etc.)."""
    mtype = get_media_type(path)
    info: Dict[str, Any] = {
        "media_type": mtype,
        "date": get_media_date(path),
    }
    if mtype == "video":
        info["duration_seconds"] = get_video_duration(path)
    else:
        info["duration_seconds"] = None
    return info


def run_pest_model(frame: "np.ndarray") -> dict:
    """Placeholder for real ML model integration (e.g. YOLOv8 plant pest/disease, HuggingFace, or custom on-device model).

    TODO for portability/other devices:
    - pip install ultralytics  # or onnxruntime for lighter
    - model = YOLO('pest_model.pt')  # trained on Brugmansia/plant pests or use PlantVillage
    - results = model(frame, conf=0.4)
    - Parse boxes/classes for aphids, mites, caterpillars, powdery mildew etc.

    Current: returns enhanced heuristic + placeholder model name.
    Call this from UI pest hooks for frame analysis.
    """
    try:
        import numpy as _np
        import cv2 as _cv2
        gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        edges = _cv2.Canny(gray, 50, 150)
        edge_ratio = float(_np.sum(edges > 0) / edges.size)
        mean_b, mean_g, mean_r = _np.mean(frame, axis=(0, 1)) if len(frame.shape) == 3 else (0, 0, 0)
        yellow_score = float((mean_r + mean_g - mean_b) / 255.0)

        issues = []
        score = 0.0
        if edge_ratio > 0.08:
            issues.append("high edge density (holes/chew/caterpillars)")
            score += 0.4
        if yellow_score > 0.65:
            issues.append("elevated yellow (spider mites/stress)")
            score += 0.3
        if mean_g < 70:
            issues.append("low green (senescence/damage)")
            score += 0.2

        # Placeholder "model" output
        return {
            "model": "placeholder_heuristic_v1 (replace with real YOLO/ONNX)",
            "pest_score": min(1.0, score),
            "issues": issues,
            "confidence": 0.65 if issues else 0.9,
            "edge_ratio": round(edge_ratio, 3),
            "yellow_score": round(yellow_score, 2),
        }
    except Exception as e:
        return {"model": "error_fallback", "pest_score": 0.0, "issues": [str(e)], "confidence": 0.0}


def diff_growth_sessions(date1: str, date2: str) -> dict:
    """Growth diffing across sessions, including 3D model proxies.
    Compares growth_log heights + media counts + basic metrics from 3D frames (if present)
    or video thumbnails (color variance as canopy proxy).
    For real 3D: could load point clouds later and compute volume/height deltas.
    """
    cfg = load_config()
    log = load_json(ROOT / "growth_log.json", default=[])
    media = load_json(MEDIA_DB, default=[])

    def find_log(d):
        for entry in log:
            if entry.get("date") == d:
                return entry
        return None

    l1 = find_log(date1) or {}
    l2 = find_log(date2) or {}
    m1 = [m for m in media if m.get("media_date") == date1]
    m2 = [m for m in media if m.get("media_date") == date2]

    h1 = l1.get("height_cm") or 0
    h2 = l2.get("height_cm") or 0
    height_delta = h2 - h1 if h1 and h2 else None

    # 3D / media proxy
    frames1 = sum(1 for m in m1 if m.get("frames_for_3d"))
    frames2 = sum(1 for m in m2 if m.get("frames_for_3d"))
    frame_delta = frames2 - frames1

    # Simple proxy: average "canopy score" from thumbs or frames (higher variance = bushier?)
    def proxy_score(items):
        scores = []
        if not CV2_AVAILABLE:
            return 0.0
        try:
            import numpy as _np  # local to avoid top level dep issues
            for m in items:
                p = m.get("thumbnail_path") or m.get("stored_path")
                if p and Path(p).exists():
                    try:
                        img = cv2.imread(str(p))
                        if img is not None:
                            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                            scores.append(float(_np.std(gray)))
                    except:
                        pass
        except:
            pass
        return sum(scores) / len(scores) if scores else 0.0

    proxy1 = proxy_score(m1)
    proxy2 = proxy_score(m2)
    proxy_delta = proxy2 - proxy1

    return {
        "date1": date1, "date2": date2,
        "height_delta_cm": round(height_delta, 1) if height_delta is not None else "N/A (no log data)",
        "media_count_delta": len(m2) - len(m1),
        "3d_frames_delta": frame_delta,
        "canopy_proxy_delta (std of gray in thumbs/frames)": round(proxy_delta, 2),
        "note": "For full 3D diff use point cloud tools on the frames_for_3d dirs. Positive proxy = more complex/bushier growth."
    }


def load_config() -> dict:
    """Load config.json with sensible defaults for 3D etc."""
    cfg = load_json(ROOT / "config.json", default={})
    cfg.setdefault("default_3d_frames", 8)
    cfg.setdefault("thumb_max_width", 160)
    cfg.setdefault("frame_max_width_for_3d", 320)
    cfg.setdefault("rapid_session_min_media", 3)
    cfg.setdefault("rapid_session_max_span_minutes", 12)
    cfg.setdefault("mirror_artifacts", False)
    cfg.setdefault("ui_port", DEFAULT_PORT)
    cfg.setdefault("api_port", DEFAULT_PORT)
    return cfg


def load_plant_context() -> dict:
    """Load structured plant knowledge from data/plant_context.json."""
    return load_json(ROOT / "data" / "plant_context.json", default={})


def load_care_actions() -> list:
    """Load care action history from data/care_actions.json."""
    return load_json(ROOT / "data" / "care_actions.json", default=[])


def get_server_ports() -> tuple[int, int]:
    """Resolve UI and API ports; API auto-increments if it would collide with UI."""
    cfg = load_config()
    ui = int(cfg.get("ui_port", DEFAULT_PORT))
    api = int(cfg.get("api_port", DEFAULT_PORT))
    if api == ui:
        api = ui + 1
    return ui, api


def local_ip() -> str:
    """Best-effort LAN IP for companion app connection hints."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def find_media_item(filename: str, media_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Look up a media DB entry by filename; optional date disambiguates duplicates."""
    media = load_json(MEDIA_DB, default=[])
    matches = [m for m in media if m.get("filename") == filename]
    if media_date:
        matches = [m for m in matches if m.get("media_date") == media_date]
    return matches[-1] if matches else None


def get_or_create_media_thumbnail(entry: Dict[str, Any]) -> Optional[Path]:
    """Return JPEG thumbnail path for a media entry; generates and caches for photos."""
    thumb = entry.get("thumbnail_path")
    if thumb:
        p = Path(thumb)
        if p.exists():
            return p

    stored = entry.get("stored_path")
    if not stored:
        return None
    src = Path(stored)
    if not src.exists():
        return None

    if get_media_type(src) == "video":
        return extract_video_thumbnail(src)

    cfg = load_config()
    max_w = int(cfg.get("thumb_max_width", 160))
    out = src.with_name(src.stem + ".thumb.jpg")
    if out.exists():
        return out

    try:
        img = Image.open(src)
        img.thumbnail((max_w, max_w * 10))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=85)
        entry["thumbnail_path"] = str(out)
        db = load_json(MEDIA_DB, default=[])
        for i, e in enumerate(db):
            if e.get("filename") == entry.get("filename") and e.get("media_date") == entry.get("media_date"):
                db[i]["thumbnail_path"] = str(out)
                break
        save_json(MEDIA_DB, db)
        return out
    except Exception:
        return src


def extract_video_thumbnail(video_path: Path, output_path: Optional[Path] = None, frame_pos: float = 0.15) -> Optional[Path]:
    """Extract a representative thumbnail frame from a video (default ~15% in).
    Resizes for size/speed using config. Saves as .jpg next to the video. Returns path or None.
    """
    if not CV2_AVAILABLE or not video_path.exists():
        return None
    cfg = load_config()
    max_w = int(cfg.get("thumb_max_width", 160))
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            total = 1
        pos = max(0, min(total - 1, int(total * frame_pos)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None

        # Resize for smaller files and faster UI
        h, w = frame.shape[:2]
        if w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA)

        if output_path is None:
            output_path = video_path.with_name(video_path.stem + ".thumb.jpg")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(output_path), frame)
        return output_path if success else None
    except Exception:
        return None


def extract_frames_for_3d(video_path: Path, num_frames: Optional[int] = None, out_dir: Optional[Path] = None) -> Optional[Path]:
    """Extract evenly spaced frames from a (short) video for photogrammetry / 3D reconstruction.
    Saves resized jpgs (for size/speed) to out_dir (defaults to models_3d/<date>/<video_stem>_frames/).
    num_frames defaults to config["default_3d_frames"].
    Returns the out_dir or None on failure.
    """
    if not CV2_AVAILABLE or not video_path.exists():
        return None
    cfg = load_config()
    if num_frames is None:
        num_frames = int(cfg.get("default_3d_frames", 8))
    max_w = int(cfg.get("frame_max_width_for_3d", 320))
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            total = 1

        if out_dir is None:
            date = get_media_date(video_path)
            stem = video_path.stem
            out_dir = ROOT / "models_3d" / date / f"{stem}_frames"
        out_dir.mkdir(parents=True, exist_ok=True)

        step = max(1, total // max(1, num_frames))
        saved = 0
        for i in range(0, total, step):
            if saved >= num_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret and frame is not None:
                # Resize for speed and smaller files
                h, w = frame.shape[:2]
                if w > max_w:
                    scale = max_w / w
                    frame = cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA)
                out_file = out_dir / f"frame_{saved:04d}.jpg"
                cv2.imwrite(str(out_file), frame)
                saved += 1
        cap.release()

        (out_dir / "README.txt").write_text(
            f"Extracted {saved} frames from {video_path.name} for 3D/photogrammetry.\n"
            f"Use with Meshroom, Scaniverse, COLMAP, or Luma AI.\n"
            f"Original video date: {get_media_date(video_path)}\n"
            f"Config used: {num_frames} frames, max width {max_w}px\n"
        )
        return out_dir if saved > 0 else None
    except Exception:
        return None


# -----------------------------
# Core: add any media (photo or video)
# -----------------------------
def add_media(
    file_path: str | Path,
    source: str = "computer",
    notes: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Add a photo or short video to the project.

    - Organizes into photos/YYYY-MM-DD/ or videos/YYYY-MM-DD/
    - Mirrors to artifacts/growth/{photos,videos}/...
    - Enforces 25 second limit for videos (rejects if longer)
    - Records rich entry in media_database.json
    - Returns the DB entry or None if rejected.
    """
    src = Path(file_path).resolve()
    if not src.exists():
        print(f"❌ File not found: {src}")
        return None

    mtype = get_media_type(src)
    media_date = get_media_date(src)

    duration: Optional[float] = None
    if mtype == "video":
        duration = get_video_duration(src)
        if duration is not None and duration > MAX_VIDEO_SECONDS:
            print(f"❌ Video too long ({duration:.1f}s). Max {MAX_VIDEO_SECONDS:.0f} seconds allowed. Not added.")
            return None
        if duration is None and CV2_AVAILABLE is False:
            print("⚠️  Could not verify video duration (OpenCV not available). Adding anyway.")

    # Target locations
    target_dir = (VIDEOS_DIR if mtype == "video" else PHOTOS_DIR) / media_date
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / src.name

    # Copy (idempotent)
    if src != dest:
        shutil.copy2(src, dest)

    cfg = load_config()
    mirror = bool(cfg.get("mirror_artifacts", False))
    art_dest = None
    if mirror:
        art_sub = "videos" if mtype == "video" else "photos"
        art_dir = ARTIFACTS_DIR / art_sub / media_date
        art_dir.mkdir(parents=True, exist_ok=True)
        art_dest = art_dir / src.name
        if src != art_dest:
            shutil.copy2(src, art_dest)

    # Build DB entry (generalized from old photo_database)
    entry: Dict[str, Any] = {
        "filename": src.name,
        "original_path": str(src),
        "stored_path": str(dest),
        "media_type": mtype,
        "duration_seconds": round(duration, 2) if duration is not None else None,
        "date_added": datetime.now().strftime("%Y-%m-%d"),
        "media_date": media_date,
        "source": source,
        "notes": notes,
        "session": media_date,
    }

    # Video-specific processing: thumbnail + 3D frames (from project vision for photogrammetry)
    if mtype == "video":
        # Thumbnail for UI
        thumb = extract_video_thumbnail(dest)
        if thumb:
            if mirror:
                art_thumb = art_dir / thumb.name
                if thumb != art_thumb:
                    shutil.copy2(thumb, art_thumb)
            entry["thumbnail_path"] = str(thumb)

        # Extract frames for 3D reconstruction (uses configurable count from config.json)
        frames_dir = extract_frames_for_3d(dest)
        if frames_dir:
            entry["frames_for_3d"] = str(frames_dir)
            # Mirror the frames dir? For simplicity copy key files or note the source.
            # We can leave the primary in models_3d/ and let user sync if needed.
            print(f"   🧊 3D frames extracted: {frames_dir} (ready for Meshroom/Polycam etc.)")

    db = load_json(MEDIA_DB, default=[])
    # naive dedup on filename + media_date
    if not any(
        e.get("filename") == entry["filename"] and e.get("media_date") == media_date
        for e in db
    ):
        db.append(entry)
        save_json(MEDIA_DB, db)

    dur_str = f" ({duration:.1f}s)" if duration else ""
    print(f"✅ Added {mtype}: {entry['filename']}{dur_str} → {dest}")
    if mirror and art_dest:
        print(f"   📦 Mirrored to artifacts: {art_dest}")
    return entry


# -----------------------------
# Convenience re-exports for old scripts
# -----------------------------
# (old add_photo.py etc. can import these)
__all__ = [
    "get_project_root",
    "load_json",
    "save_json",
    "load_config",
    "load_plant_context",
    "load_care_actions",
    "local_ip",
    "find_media_item",
    "get_or_create_media_thumbnail",
    "get_exif_datetime",
    "get_video_duration",
    "get_video_creation_time",
    "get_media_date",
    "get_media_type",
    "get_media_info",
    "extract_video_thumbnail",
    "extract_frames_for_3d",
    "run_pest_model",
    "diff_growth_sessions",
    "add_media",
    "ROOT",
    "MEDIA_DB",
    "PHOTOS_DIR",
    "VIDEOS_DIR",
    "ARTIFACTS_DIR",
    "CV2_AVAILABLE",
    "MAX_VIDEO_SECONDS",
    "DEFAULT_PORT",
    "get_server_ports",
]
