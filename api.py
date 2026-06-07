#!/usr/bin/env python3
"""
growth REST API — companion backend for iPhone / other clients on the same network.

Run: uvicorn api:app --host 0.0.0.0 --port 21322
Or:  python3 main.py api
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from utils import (
    ROOT,
    MEDIA_DB,
    MAX_VIDEO_SECONDS,
    add_media,
    find_media_item,
    get_media_type,
    get_or_create_media_thumbnail,
    get_video_duration,
    load_care_actions,
    load_config,
    load_json,
    load_plant_context,
    local_ip,
    get_server_ports,
)

app = FastAPI(title="growth API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "project_root": str(ROOT)}


@app.get("/api/v1/status")
def status():
    config = load_config()
    log = load_json(ROOT / "growth_log.json", default=[])
    media = load_json(MEDIA_DB, default=[])
    latest = log[-1] if log else {}
    return {
        "plant_name": config.get("plant_name"),
        "species": config.get("species"),
        "location": config.get("location"),
        "latest_entry": latest,
        "media_count": len(media),
        "goals": config.get("goals", []),
    }


@app.get("/api/v1/instructions")
def instructions():
    log = load_json(ROOT / "growth_log.json", default=[])
    if not log:
        raise HTTPException(404, "No growth log entries")
    latest = log[-1]
    path = ROOT / "reports" / f"instructions_{latest['date']}.md"
    if path.exists():
        return {"date": latest["date"], "markdown": path.read_text()}
    raise HTTPException(404, "No instructions file; run create_instructions.py")


def _thumbnail_url(entry: dict) -> str:
    name = entry.get("filename", "")
    date = entry.get("media_date", "")
    qs = f"?date={date}" if date else ""
    return f"/api/v1/media/{name}/thumbnail{qs}"


@app.get("/api/v1/server/info")
def server_info():
    ui_port, api_port = get_server_ports()
    ip = local_ip()
    return {
        "lan_ip": ip,
        "api_port": api_port,
        "ui_port": ui_port,
        "api_base": f"https://{ip}:{api_port}/api/v1",
        "ui_base": f"https://{ip}:{ui_port}",
        "https_recommended": True,
        "thumbnail_pattern": "/api/v1/media/{filename}/thumbnail?date={media_date}",
    }


@app.get("/api/v1/media")
def list_media(limit: int = 20):
    media = sorted(
        load_json(MEDIA_DB, default=[]),
        key=lambda m: m.get("media_date", ""),
        reverse=True,
    )[:limit]
    items = []
    for m in media:
        item = dict(m)
        item["thumbnail_url"] = _thumbnail_url(m)
        items.append(item)
    return {"items": items, "count": len(items)}


@app.get("/api/v1/media/{filename}/thumbnail")
def media_thumbnail(filename: str, date: Optional[str] = Query(None, description="Session date YYYY-MM-DD")):
    entry = find_media_item(filename, date)
    if not entry:
        raise HTTPException(404, detail=f"Media not found: {filename}")

    thumb = get_or_create_media_thumbnail(entry)
    if not thumb or not thumb.exists():
        raise HTTPException(404, detail="Thumbnail not available")

    media_type = "image/jpeg" if thumb.suffix.lower() in {".jpg", ".jpeg"} else "application/octet-stream"
    return FileResponse(thumb, media_type=media_type, filename=thumb.name)


@app.get("/api/v1/context")
def plant_context():
    return {
        "config": load_config(),
        "plant_context": load_plant_context(),
        "care_actions": load_care_actions(),
    }


@app.post("/api/v1/media/upload")
async def upload_media(
    files: list[UploadFile] = File(...),
    source: str = Form("iphone"),
    notes: str = Form(""),
):
    if not files:
        raise HTTPException(400, "No files provided")

    added = []
    rejected = []

    for upload in files:
        suffix = Path(upload.filename or "upload").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(upload.file, tmp)
            tmp_path = Path(tmp.name)

        try:
            if get_media_type(tmp_path) == "video":
                duration = get_video_duration(tmp_path)
                if duration is not None and duration > MAX_VIDEO_SECONDS:
                    rejected.append({
                        "filename": upload.filename,
                        "reason": f"Video {duration:.1f}s exceeds {MAX_VIDEO_SECONDS:.0f}s limit",
                    })
                    continue

            entry = add_media(tmp_path, source=source, notes=notes)
            if entry:
                added.append(entry)
            else:
                rejected.append({"filename": upload.filename, "reason": "add_media rejected"})
        finally:
            tmp_path.unlink(missing_ok=True)

    return {"added": added, "rejected": rejected, "added_count": len(added)}