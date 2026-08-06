import os
import gc
import shutil
import threading
import sys
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

TEMP_AUDIO_DIR = BASE_DIR / "temp" / "audio"
TEMP_SEP_DIR = BASE_DIR / "temp" / "separated"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TEMP_SEP_DIR.mkdir(parents=True, exist_ok=True)

from server.downloader import download_audio_only
from server.separator import separate_audio, get_device

app = FastAPI(title="YouTube Instrument Remover Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TASKS_LOCK = threading.Lock()
TASKS: Dict[str, dict] = {}


class ProcessRequest(BaseModel):
    url: str
    video_id: str
    quality: str = "fast"
    device: str = "auto"


def sanitize_id(vid: str) -> str:
    cleaned = "".join(c for c in vid if c.isalnum() or c in ("-", "_"))
    return cleaned if cleaned else "default_video"


def run_pipeline(url: str, video_id: str, quality: str = "fast", device: str = "auto"):
    clean_id = sanitize_id(video_id)
    out_dir = TEMP_SEP_DIR / clean_id
    vocal_file = out_dir / "vocals.wav"

    if vocal_file.exists():
        with TASKS_LOCK:
            TASKS[clean_id] = {"status": "ready", "progress": 100, "error": None}
        return

    try:
        with TASKS_LOCK:
            TASKS[clean_id] = {"status": "downloading", "progress": 25, "error": None}

        # 1. Download audio only
        raw_audio_file = TEMP_AUDIO_DIR / f"{clean_id}.wav"
        success = download_audio_only(url, clean_id, raw_audio_file)
        if not success:
            with TASKS_LOCK:
                TASKS[clean_id] = {"status": "error", "progress": 0, "error": "Audio download failed"}
            return

        # 2. Separate vocals
        with TASKS_LOCK:
            TASKS[clean_id] = {"status": "separating", "progress": 60, "error": None}

        vocal_p, inst_p = separate_audio(raw_audio_file, out_dir, quality=quality, device_setting=device)

        # 3. Clean raw input file to save disk space
        try:
            if raw_audio_file.exists():
                os.remove(raw_audio_file)
        except Exception:
            pass

        with TASKS_LOCK:
            TASKS[clean_id] = {"status": "ready", "progress": 100, "error": None}

    except Exception as e:
        print(f"[Pipeline Error] {e}", flush=True)
        with TASKS_LOCK:
            TASKS[clean_id] = {"status": "error", "progress": 0, "error": str(e)}


@app.post("/process")
def process_video(req: ProcessRequest):
    clean_id = sanitize_id(req.video_id)
    with TASKS_LOCK:
        if clean_id not in TASKS or TASKS[clean_id]["status"] == "error":
            TASKS[clean_id] = {"status": "queued", "progress": 10, "error": None}
            thread = threading.Thread(
                target=run_pipeline,
                args=(req.url, req.video_id, req.quality, req.device),
                daemon=True,
            )
            thread.start()

    return {"status": "started", "video_id": clean_id}


@app.get("/status/{video_id}")
def get_status(video_id: str):
    clean_id = sanitize_id(video_id)
    with TASKS_LOCK:
        if clean_id not in TASKS:
            vocal_file = TEMP_SEP_DIR / clean_id / "vocals.wav"
            if vocal_file.exists():
                return {"status": "ready", "progress": 100, "error": None}
            return {"status": "idle", "progress": 0, "error": None}
        return TASKS[clean_id]


@app.get("/audio/{video_id}/vocals")
def get_vocals_audio(video_id: str):
    clean_id = sanitize_id(video_id)
    vocal_file = TEMP_SEP_DIR / clean_id / "vocals.wav"
    if not vocal_file.exists():
        raise HTTPException(status_code=404, detail="Vocal audio file not found")
    return FileResponse(
        str(vocal_file),
        media_type="audio/wav",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )


def get_dir_size_mb(path: Path) -> float:
    total_bytes = 0
    if path.exists():
        for p in path.rglob("*"):
            if p.is_file():
                total_bytes += p.stat().st_size
    return round(total_bytes / (1024 * 1024), 2)


@app.get("/cache_size")
def get_cache_size():
    sep_size = get_dir_size_mb(TEMP_SEP_DIR)
    audio_size = get_dir_size_mb(TEMP_AUDIO_DIR)
    return {"total_mb": round(sep_size + audio_size, 2)}


@app.post("/cleanup_all")
def cleanup_all_cache():
    initial_size = get_dir_size_mb(TEMP_SEP_DIR) + get_dir_size_mb(TEMP_AUDIO_DIR)
    shutil.rmtree(TEMP_SEP_DIR, ignore_errors=True)
    shutil.rmtree(TEMP_AUDIO_DIR, ignore_errors=True)
    TEMP_SEP_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with TASKS_LOCK:
        TASKS.clear()
    return {"status": "cleaned", "freed_mb": round(initial_size, 2)}


@app.post("/cleanup/{video_id}")
def cleanup_temp(video_id: str):
    clean_id = sanitize_id(video_id)
    target_dir = TEMP_SEP_DIR / clean_id
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    raw_audio = TEMP_AUDIO_DIR / f"{clean_id}.wav"
    if raw_audio.exists():
        try:
            os.remove(raw_audio)
        except Exception:
            pass
    with TASKS_LOCK:
        if clean_id in TASKS:
            del TASKS[clean_id]
    return {"status": "cleaned"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
