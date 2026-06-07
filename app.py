import streamlit as st
import json
import tempfile
from pathlib import Path
from datetime import datetime

import zoneinfo
from datetime import datetime as dtmod

from utils import (
    ROOT,
    MEDIA_DB,
    PHOTOS_DIR,
    VIDEOS_DIR,
    ARTIFACTS_DIR,
    get_exif_datetime,
    get_media_type,
    get_video_duration,
    add_media,
    load_json,
    load_plant_context,
    load_care_actions,
    extract_video_thumbnail,
    extract_frames_for_3d,
    run_pest_model,
    diff_growth_sessions,
    MAX_VIDEO_SECONDS,
    get_server_ports,
)


def _save_upload_to_temp(uploaded) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="growth_upload_"))
    tmp_path = tmp_dir / uploaded.name
    with open(tmp_path, "wb") as f:
        f.write(uploaded.getbuffer())
    return tmp_path

# Keep astral for sun analysis (already in requirements)
try:
    from astral import LocationInfo
    from astral.sun import azimuth, elevation
    ASTRAL_AVAILABLE = True
except Exception:
    ASTRAL_AVAILABLE = False

def analyze_rapid_session_sun(media_paths: list[Path], config: dict):
    """
    If 3+ media items (photos or videos) were captured in a short window,
    compute sun position + shadow using astral + config lat/lon (from the conversation history).
    Only photos with EXIF DateTimeOriginal contribute to the time calculation.
    """
    if not media_paths or len(media_paths) < 3:
        return None
    if not ASTRAL_AVAILABLE:
        return {"note": "astral not installed; using approximate values", "azimuth": "~76-95° (East)"}

    times = []
    for p in media_paths:
        t = get_exif_datetime(p)
        if t:
            times.append(t)

    if len(times) < 3:
        return None

    times.sort()
    span = (times[-1] - times[0]).total_seconds() / 60.0
    if span > 12:
        return None

    rep_time = times[len(times) // 2]

    try:
        lat = float(config.get("latitude", 35.2271))
        lon = float(config.get("longitude", -80.8431))
        city = LocationInfo(
            latitude=lat, longitude=lon, timezone="America/New_York",
            name=config.get("location", "Charlotte")
        )
        tz = zoneinfo.ZoneInfo("America/New_York")

        az = azimuth(city.observer, rep_time)
        el = elevation(city.observer, rep_time)
        shadow_bearing = (az + 180) % 360

        def cardinal(deg):
            dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            return dirs[int((deg + 11.25) / 22.5) % 16]

        shadow_dir = cardinal(shadow_bearing)
        weather_note = "Clear/bright (sharp shadows)" if el > 15 else "Low sun / longer shadows"

        return {
            "time": rep_time.strftime("%Y-%m-%d %H:%M %Z"),
            "num_media": len(times),
            "span_minutes": round(span, 1),
            "azimuth": round(az, 1),
            "elevation": round(el, 1),
            "shadow_bearing": round(shadow_bearing, 1),
            "shadow_direction": shadow_dir,
            "weather_note": weather_note,
            "location": f"{lat:.4f}, {lon:.4f}",
        }
    except Exception as e:
        return {"error": str(e)}

st.set_page_config(page_title="growth - Plant Tracker", layout="wide")
st.title("🌱 growth — Plant Digital Twin")

media_db = load_json(MEDIA_DB, default=[])
growth_log = load_json(ROOT / "growth_log.json", default=[])
config = load_json(ROOT / "config.json", default={})
plant_ctx = load_plant_context()
care_actions = load_care_actions()

st.sidebar.header("Project: growth")
st.sidebar.write(f"**Plant:** {config.get('plant_name', 'Brugmansia')}")
st.sidebar.write(f"**Location:** {config.get('location', 'Charlotte, NC')}")
st.sidebar.caption(f"Root: {ROOT}")
ui_port, api_port = get_server_ports()
try:
    import socket
    _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _s.connect(("8.8.8.8", 80))
    _lan_ip = _s.getsockname()[0]
    _s.close()
except Exception:
    _lan_ip = "127.0.0.1"
st.sidebar.caption(f"iPhone: http://{_lan_ip}:{ui_port}")
st.sidebar.caption(f"API: http://{_lan_ip}:{api_port}/api/v1")
st.sidebar.caption("Change port: `./run.sh --ui-port 21322 --save-ports`")

st.header("Current Status")
if growth_log:
    latest = growth_log[-1]
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Latest Height", f"{latest.get('height_cm', 'N/A')} cm")
        st.write(f"**Date:** {latest['date']}")
    with col2:
        st.metric("Canopy Width", f"{latest.get('width_cm', config.get('current_width_cm', 'N/A'))} cm")
        st.write(f"**Lean:** {latest.get('lean_direction', 'east')}")
    with col3:
        roots = plant_ctx.get("root_system", {})
        st.metric("Root Spread", f"{roots.get('spread_diameter_ft', '4-6')} ft")
        recent_media = [m for m in media_db if m.get("media_date") == latest.get("date")]
        st.write(f"**Media in session:** {len(recent_media)}")
    st.write(f"**Notes:** {latest.get('notes', '')}")
    st.caption(f"Goals: {'; '.join(config.get('goals', []))}")

with st.expander("Plant context (from Brugmansia June 2026 session)"):
    if plant_ctx:
        st.write(f"**Species:** {plant_ctx.get('species', 'N/A')}")
        st.write(f"**Size method:** {plant_ctx.get('size_estimates', {}).get('method', 'N/A')}")
        proto = plant_ctx.get("photo_protocol", {})
        st.write(f"**Photo protocol:** {proto.get('device', 'iPhone')} {proto.get('magnification', '1x')} — {proto.get('walk_pattern', 'clockwise walk')}")
        st.write(f"**Base seedlings:** {plant_ctx.get('companion_plants', {}).get('base_seedlings', 'N/A')}")
        if care_actions:
            st.write("**Recent care actions:**")
            for act in care_actions[-3:]:
                st.caption(f"{act.get('date')}: {act.get('description', act.get('action', ''))}")
    else:
        st.info("No plant_context.json yet. Run scripts or add data/plant_context.json.")

# Persistent "Recent Media with Thumbs" browser (reorganized for usability)
st.header("📷 Recent Media Browser (with thumbnails)")
try:
    recent_media = sorted(load_json(MEDIA_DB, default=[]), key=lambda x: x.get("media_date", ""), reverse=True)[:20]
    if recent_media:
        cols = st.columns(4)
        for idx, m in enumerate(recent_media):
            with cols[idx % 4]:
                st.write(f"**{m.get('media_date')}** - {m.get('filename')}")
                if m.get("thumbnail_path") and Path(m["thumbnail_path"]).exists():
                    st.image(m["thumbnail_path"], width=120)
                elif m.get("media_type") == "video":
                    st.video(m.get("stored_path"), start_time=0)  # fallback
                else:
                    if m.get("stored_path") and Path(m["stored_path"]).exists():
                        st.image(m["stored_path"], width=120)
                meta = f"{m.get('media_type', 'media')}"
                if m.get("duration_seconds"):
                    meta += f" ({m['duration_seconds']}s)"
                st.caption(meta)
                if m.get("notes"):
                    st.caption(m["notes"][:50])
                if m.get("frames_for_3d"):
                    st.caption(f"3D frames: {Path(m['frames_for_3d']).name}")
    else:
        st.info("No media yet. Upload some photos or short videos above.")
except Exception as e:
    st.error(f"Recent media browser error: {e}")

# Growth diffing across 3D models / sessions (new feature)
st.header("📈 Growth Diffing (incl. 3D proxies)")
try:
    all_dates = sorted({m.get("media_date") for m in load_json(MEDIA_DB, []) if m.get("media_date")}, reverse=True)
    if len(all_dates) >= 2:
        c1, c2 = st.columns(2)
        with c1:
            d1 = st.selectbox("Session 1 (earlier)", all_dates, index=min(1, len(all_dates)-1))
        with c2:
            d2 = st.selectbox("Session 2 (later)", all_dates, index=0)
        if st.button("Compute Growth Diff"):
            diff = diff_growth_sessions(d1, d2)  # from utils
            st.json(diff)
            st.caption("Positive canopy proxy delta often means bushier growth. Use the extracted 3D frame folders for full photogrammetry diffs.")
    else:
        st.info("Need at least two dated media sessions for diffing (add more photos/videos over time).")
except Exception as e:
    st.error(f"Diff error: {e}")

st.header("📸 Upload Media")

photo_tab, video_tab = st.tabs(["Photos", "Videos (≤25 s)"])

with photo_tab:
    st.caption("Drag & drop or browse — Mac Finder, iPhone Files, or Share sheet → Save to Files.")
    uploaded_photos = st.file_uploader(
        "Photos",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True,
        key="photo_uploader",
        label_visibility="collapsed",
    )

with video_tab:
    st.caption(
        "Drag & drop or browse short clips. iPhone: record in Camera, then Share → Save to Files "
        "and pick here in Safari. Mac: Finder or QuickTime export. **Max 25 seconds.**"
    )
    uploaded_videos = st.file_uploader(
        "Videos",
        type=["mp4", "mov", "m4v"],
        accept_multiple_files=True,
        key="video_uploader",
        label_visibility="collapsed",
    )

uploaded_files = list(uploaded_photos or []) + list(uploaded_videos or [])

if uploaded_files:
    added_entries = []
    temp_files = []  # for cleanup
    rejected_videos = []

    for uploaded in uploaded_files:
        tmp_path = _save_upload_to_temp(uploaded)
        temp_files.append(tmp_path)

        if get_media_type(tmp_path) == "video":
            duration = get_video_duration(tmp_path)
            if duration is not None and duration > MAX_VIDEO_SECONDS:
                rejected_videos.append((uploaded.name, duration))
                st.error(
                    f"**{uploaded.name}** is {duration:.1f}s — over the {MAX_VIDEO_SECONDS:.0f}s limit. "
                    "Trim in Photos (iPhone) or QuickTime (Mac) and re-upload."
                )
                continue
            if duration is not None:
                st.caption(f"🎥 {uploaded.name} — {duration:.1f}s (within limit)")

        entry = add_media(tmp_path, source="upload", notes="")
        if entry:
            added_entries.append(entry)
        else:
            st.warning(f"Skipped {uploaded.name} (see terminal / reason above)")

    # Collect final stored paths for this batch (for sun analysis etc.)
    batch_paths = [Path(e["stored_path"]) for e in added_entries]

    # Reload media db (add_media wrote it)
    media_db = load_json(MEDIA_DB, default=[])

    # --- Rapid session sun/shadow analysis (from full conversation history) ---
    if len(added_entries) > 3:
        st.info("Rapid media session detected (>3 items)")
        sun_info = analyze_rapid_session_sun(batch_paths, config)
        st.write("**Sun Position & Shadow Analysis (Charlotte, NC)**")
        if sun_info and "error" not in sun_info and "note" not in sun_info:
            st.write(f"- Session time (median EXIF from photos): {sun_info['time']}")
            st.write(f"- Media items with timestamps: {sun_info.get('num_media', len(batch_paths))} (span ~{sun_info['span_minutes']} min)")
            st.write(f"- Sun Azimuth: {sun_info['azimuth']}° | Elevation: {sun_info['elevation']}°")
            st.write(f"- Shadow: ~{sun_info['shadow_bearing']}° → {sun_info['shadow_direction']}")
            st.write(f"- Light inference: {sun_info['weather_note']}")
            st.caption(f"Location: {sun_info['location']} (from config.json)")
        else:
            note = (sun_info or {}).get("note", "no usable EXIF times or span too large")
            st.write("- Sun Azimuth: ~76–95° (East) [real calc requires good EXIF on photos in the batch]")
            st.caption(f"Fallback: {note}")

    if rejected_videos:
        st.warning(f"{len(rejected_videos)} video(s) rejected for exceeding {MAX_VIDEO_SECONDS:.0f}s.")

    # --- Previews + pest/demo section (works for photos and videos) ---
    st.subheader("Uploaded Previews + Quick Check")
    for i, up in enumerate(uploaded_files):
        mtype = get_media_type(Path(up.name))
        matching_entry = next((e for e in added_entries if e.get("filename") == up.name), None)
        if mtype == "video":
            caption = f"🎥 {up.name}"
            if matching_entry:
                vcol, tcol = st.columns([2, 1])
                with vcol:
                    st.video(up, start_time=0)
                with tcol:
                    thumb_p = matching_entry.get("thumbnail_path")
                    if thumb_p and Path(thumb_p).exists():
                        st.image(str(thumb_p), caption="Extracted thumbnail")
                    else:
                        st.caption("Thumbnail pending")
                if matching_entry.get("duration_seconds"):
                    st.caption(f"Duration: {matching_entry['duration_seconds']}s")
            else:
                st.video(up, start_time=0, caption=up.name)
        else:
            st.image(up, width=250, caption=up.name)
            caption = up.name

        if st.checkbox(f"Inspect {caption}", key=f"inspect_{i}"):
            if mtype == "video":
                matching_entry = next((e for e in added_entries if e.get("filename") == up.name), None)
                video_path = Path(matching_entry["stored_path"]) if matching_entry else None

                if video_path and video_path.exists():
                    st.write("**Video frame pest/damage analysis (sampled frames):**")
                    try:
                        import cv2
                        import numpy as np
                        cap = cv2.VideoCapture(str(video_path))
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 30)
                        sample_positions = [int(total * p) for p in (0.1, 0.5, 0.85)]
                        for idx, pos in enumerate(sample_positions):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, min(pos, total-1))
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                st.image(frame_rgb, width=220, caption=f"Frame ~{pos}")
                                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                                edges = cv2.Canny(gray, 50, 150)
                                edge_ratio = np.sum(edges > 0) / edges.size
                                mean_b, mean_g, mean_r = np.mean(frame, axis=(0,1))
                                yellow_score = (mean_r + mean_g - mean_b) / 255.0
                                issues = []
                                if edge_ratio > 0.08:
                                    issues.append("high edge density (possible holes/chew marks/caterpillars)")
                                if yellow_score > 0.65:
                                    issues.append("elevated yellow (possible spider mites/stress/chlorosis)")
                                if mean_g < 80:
                                    issues.append("low green (senescence or heavy damage)")
                                model_res = run_pest_model(frame)
                                if model_res.get("issues"):
                                    st.warning(f"Frame {idx+1} [{model_res['model']}]: {', '.join(model_res['issues'])} (score={model_res['pest_score']:.2f}, conf={model_res.get('confidence',0):.2f})")
                                else:
                                    st.success(f"Frame {idx+1} [{model_res['model']}]: Clean (score={model_res['pest_score']:.2f})")
                        cap.release()
                    except Exception as e:
                        st.info(f"Frame analysis unavailable (cv2/numpy issue): {e}")
                    st.caption("This is a lightweight hook. Future: integrate YOLO/PlantVillage model on extracted frames.")
                else:
                    st.info("Demo only — hook real CV / pest model here (YOLO, etc. from the project vision). Common on Brugmansia: aphids, spider mites, caterpillars, leaf holes.")
            else:
                st.info("Demo only — hook real CV / pest model here (YOLO, etc. from the project vision). Common on Brugmansia: aphids, spider mites, caterpillars, leaf holes.")

    video_entries = [e for e in added_entries if e.get("media_type") == "video" and e.get("thumbnail_path")]
    if video_entries:
        st.write("**Video thumbnails (auto-extracted):**")
        for e in video_entries:
            thumb_p = Path(e["thumbnail_path"])
            if thumb_p.exists():
                st.image(str(thumb_p), width=160, caption=f"{e['filename']} thumb")

    if added_entries:
        st.success(f"✅ Added {len(added_entries)} media item(s) via utils.add_media (dated folders + artifacts/growth/ + media_database.json)")
        dates_used = sorted({e["media_date"] for e in added_entries})
        st.caption(f"Folders: photos/ or videos/ under {', '.join(dates_used)} (also mirrored to artifacts)")

        video_3d = [e for e in added_entries if e.get("media_type") == "video" and e.get("frames_for_3d")]
        if video_3d:
            st.info("🧊 3D photogrammetry frames extracted automatically for your video(s).")
            for e in video_3d:
                frames_path = e.get("frames_for_3d")
                st.write(f"- {e['filename']}: frames saved to `{frames_path}`")
                st.caption("Feed these evenly-spaced frames into Meshroom, Scaniverse, COLMAP, Polycam or Luma AI for 3D model of the plant. Great for tracking structural changes over time.")
            if st.button("Re-extract more 3D frames from latest video (higher density)"):
                for e in video_3d:
                    vpath = Path(e["stored_path"])
                    if vpath.exists():
                        new_dir = extract_frames_for_3d(vpath, num_frames=20)
                        if new_dir:
                            st.success(f"Re-extracted 20 frames to {new_dir}")

    for t in temp_files:
        try:
            t.unlink(missing_ok=True)
            t.parent.rmdir()
        except Exception:
            pass

st.header("📋 Care Instructions")
if st.button("Generate / Refresh Instructions"):
    latest_report = ROOT / "reports" / f"instructions_{growth_log[-1]['date'] if growth_log else 'latest'}.md"
    if latest_report.exists():
        st.markdown(latest_report.read_text())
    else:
        st.markdown(f"""
**Current Height:** {growth_log[-1].get('height_cm', 'N/A')} cm (as of {growth_log[-1]['date'] if growth_log else 'N/A'})

### Recommended (from config)
- Focus tip-pinching on tallest eastern stems to counter lean.
- Balanced fertilizer weekly during growth.
- Keep root zone moist + mulch.
- Monitor brassica seedlings + pests on new growth.

**Goals:** {', '.join(config.get('goals', []))}
""")
    st.caption("Tip: run `python3 scripts/create_instructions.py` from CLI for fresh generated file + artifacts copy.")
