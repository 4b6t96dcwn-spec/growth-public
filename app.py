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


PLACEHOLDER_TRUNCATED