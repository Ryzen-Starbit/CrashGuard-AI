import sys
import time
import uuid
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from predict import predict as run_pipeline
from src.alerts.nearby import load_services, validate_location, find_nearest
from src.alerts.dispatch import dispatch_alert, read_alert_log

UPLOAD_DIR = ROOT / "backend" / "uploads"
PROCESSED_DIR = ROOT / "data" / "processed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = 100
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_STORED_UPLOADS = 5
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
CHUNK_SIZE = 1024 * 1024

STAGE_LABELS = {
    "probing": "Reading video...",
    "detecting": "Detecting and tracking vehicles (YOLOv8n + ByteTrack)...",
    "features": "Measuring overlap, braking and stopping...",
    "anomaly": "Checking for box deformation and abrupt track changes...",
    "scoring": "Scoring every half-second with the classifier...",
}

app = FastAPI(title="CrashGuard AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS = {}
ALERT_LOCK = threading.Lock()
PIPELINE_LOCK = threading.Lock()


def _set_progress(job: dict, stage: str, pct: float, frame=None, total=None):
    job["stage"] = stage
    job["stage_label"] = STAGE_LABELS.get(stage, "Processing...")
    job["progress_pct"] = round(max(job.get("progress_pct", 0), pct), 1)
    elapsed = time.time() - job["started_at"]
    job["elapsed_seconds"] = round(elapsed, 1)
    if job["progress_pct"] >= 8:
        job["estimated_seconds"] = round(elapsed / (job["progress_pct"] / 100))
    if frame is not None and total:
        job["frame_progress"] = {"frame": int(frame), "total_frames": int(total)}


def _process_job(job_id: str, video_path: Path):
    job = JOBS[job_id]
    with PIPELINE_LOCK:
        job["status"] = "processing"
        job["started_at"] = time.time()
        _set_progress(job, "probing", 1)
        try:
            verdict = run_pipeline(
                str(video_path),
                processed_dir=str(PROCESSED_DIR),
                keep_intermediate=False,
                progress=lambda s, p, f=None, t=None: _set_progress(job, s, p, f, t),
            )
            if verdict is None:
                job["status"] = "error"
                job["error"] = "No vehicle activity detected in this video."
                return
            job["result"] = verdict
            job["status"] = "done"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            traceback.print_exc()


def _cleanup_old_uploads():
    files = sorted(
        (p for p in UPLOAD_DIR.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    busy = {Path(j["video_path"]) for j in JOBS.values() if j["status"] in ("queued", "processing")}
    for old in files[MAX_STORED_UPLOADS:]:
        if old not in busy:
            old.unlink(missing_ok=True)


def _save_upload(file: UploadFile, dest: Path):
    size = 0
    with open(dest, "wb") as out:
        while chunk := file.file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Video is larger than {MAX_UPLOAD_MB} MB.")
            out.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")


def _is_readable_video(path: Path) -> bool:
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    return ok


@app.post("/api/analyze")
def analyze(
    file: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
):
    loc_error = validate_location(lat, lon)
    if loc_error:
        raise HTTPException(status_code=400, detail=loc_error)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

    job_id = uuid.uuid4().hex[:12]
    video_path = UPLOAD_DIR / f"{job_id}{ext}"
    _save_upload(file, video_path)
    if not _is_readable_video(video_path):
        video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not read this video. Try an MP4 (H.264) file.")

    JOBS[job_id] = {
        "status": "queued",
        "filename": file.filename,
        "video_path": str(video_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon},
        "emergency": find_nearest(lat, lon),
        "alert": None,
        "progress_pct": 0,
    }
    _cleanup_old_uploads()
    threading.Thread(target=_process_job, args=(job_id, video_path), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id")
    if job["status"] == "processing":
        job["elapsed_seconds"] = round(time.time() - job["started_at"], 1)
    return {
        "job_id": job_id,
        "status": job["status"],
        "filename": job["filename"],
        "stage": job.get("stage"),
        "stage_label": job.get("stage_label"),
        "progress_pct": job.get("progress_pct", 0),
        "elapsed_seconds": job.get("elapsed_seconds"),
        "estimated_seconds": job.get("estimated_seconds"),
        "frame_progress": job.get("frame_progress"),
        "result": job.get("result"),
        "error": job.get("error"),
        "location": job.get("location"),
        "emergency": job.get("emergency"),
        "alert": job.get("alert"),
    }


@app.get("/api/video/{job_id}")
def get_video(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id")
    path = Path(job["video_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video was cleaned up. Upload it again to replay.")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/services")
def services():
    return load_services()


@app.get("/api/nearby")
def nearby(lat: float, lon: float):
    loc_error = validate_location(lat, lon)
    if loc_error:
        raise HTTPException(status_code=400, detail=loc_error)
    return find_nearest(lat, lon)


class AlertRequest(BaseModel):
    manual_override: bool = False
    operator_note: Optional[str] = ""


@app.post("/api/alert/{job_id}")
def send_alert(job_id: str, body: AlertRequest = AlertRequest()):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id")
    if job["status"] != "done" or not job.get("result"):
        raise HTTPException(status_code=409, detail="Analysis is not finished yet.")
    verdict = job["result"]
    if not verdict.get("accident_detected") and not body.manual_override:
        raise HTTPException(
            status_code=400,
            detail="Model did not flag an accident. Set manual_override=true to send anyway.",
        )
    with ALERT_LOCK:
        if job.get("alert"):
            return {**job["alert"], "already_sent": True}
        record = dispatch_alert(
            job_id=job_id,
            clip_name=job["filename"],
            verdict=verdict,
            emergency=job["emergency"],
            manual_override=body.manual_override,
            operator_note=body.operator_note or "",
        )
        job["alert"] = record
    return {**record, "already_sent": False}


@app.get("/api/alerts")
def alerts(limit: int = 50):
    return read_alert_log(limit)


@app.get("/api/health")
def health():
    return {"status": "ok", "jobs_in_memory": len(JOBS)}
