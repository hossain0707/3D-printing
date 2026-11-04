"""Owner-scoped realistic reconstruction API; no fake previews, no simulated checkout."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import shutil
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

from .db import connect, initialize
from .settings import Settings

log = logging.getLogger(__name__)
settings = Settings.load()
initialize(settings.data_dir)
app = FastAPI(
    title="MINIMO Realistic Replica API", version="2.0.0",
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Project-Token", "X-Admin-Key"],
)

MAX_PHOTOS = 40
MIN_PHOTOS = 12
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_BYTES = 240 * 1024 * 1024
MAX_RESOLUTION = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_RESOLUTION
RATE: defaultdict[str, deque[float]] = defaultdict(deque)
RATE_LOCK = Lock()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(token: str) -> str:
    return hmac.new(settings.token_pepper.encode("utf-8"),
                    token.encode("utf-8"), hashlib.sha256).hexdigest()


def owner_token(x_project_token: Annotated[str | None, Header()] = None) -> str | None:
    return x_project_token


def authorize(pid: str, token: str | None) -> sqlite3.Row:
    if not token:
        raise HTTPException(401, "Project access token required")
    with connect(settings.data_dir) as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if row is None or not hmac.compare_digest(fingerprint(token), row["token_hash"]):
        raise HTTPException(404, "Project not found")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(410, "Project has expired")
    return row


def artifact_path(relative: str) -> Path:
    """Resolve server-owned relative artifacts under private persistent storage."""
    path = Path(relative)
    if path.is_absolute():
        raise HTTPException(500, "Invalid artifact location")
    resolved = (settings.data_dir / path).resolve()
    if not resolved.is_relative_to(settings.data_dir):
        raise HTTPException(500, "Artifact location escapes private storage")
    return resolved


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not settings.admin_key:
        raise HTTPException(503, "Operator access is not configured")
    if not x_admin_key or not hmac.compare_digest(settings.admin_key, x_admin_key):
        raise HTTPException(401, "Unauthorized")


def throttle(ip: str):
    now = time.monotonic()
    with RATE_LOCK:
        history = RATE[ip]
        while history and history[0] < now - 3600:
            history.popleft()
        if len(history) >= 4:
            raise HTTPException(429, "Upload rate limit reached")
        history.append(now)


@app.middleware("http")
async def private_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/v2/health")
def health():
    return {
        "status": "ok",
        "pipeline": "real_multi_view_photogrammetry",
        "upload_enabled": settings.enable_uploads,
        "colmap_installed": bool(shutil.which(settings.colmap)),
        "blender_installed": bool(shutil.which(settings.blender)),
        "payment_enabled": False,
        "printer_certified": False,
        "min_photos": MIN_PHOTOS,
        "max_photos": MAX_PHOTOS,
    }


def decode_photo(raw: bytes, content_type: str | None) -> tuple[bytes, int, int, str]:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "JPEG, PNG or WebP images only")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(415, "File content is not an accepted image")
            if img.width * img.height > MAX_RESOLUTION:
                raise HTTPException(413, "Image resolution too large")
            image = ImageOps.exif_transpose(img).convert("RGB")
            image.thumbnail((3000, 3000))
            w, h = image.size
            if w < 400 or h < 400:
                raise HTTPException(422, "Each photograph must be at least 400 pixels in both dimensions")
            cleaned = io.BytesIO()
            image.save(cleaned, "JPEG", quality=92, optimize=True)
            return cleaned.getvalue(), w, h, hashlib.sha256(cleaned.getvalue()).hexdigest()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise HTTPException(422, "Image could not be decoded safely")


@app.post("/api/v2/projects", status_code=201)
async def create_project(request: Request,
                         consent: bool = Form(...),
                         photos: list[UploadFile] = File(...)):
    if not settings.enable_uploads:
        raise HTTPException(503, "Private image intake is not enabled on the processing server")
    if not consent:
        raise HTTPException(422, "Consent to process photographs is required")
    if not MIN_PHOTOS <= len(photos) <= MAX_PHOTOS:
        raise HTTPException(422, f"Upload {MIN_PHOTOS}–{MAX_PHOTOS} distinct overlapping photographs")
    throttle(request.client.host if request.client else "unknown")
    with connect(settings.data_dir) as db:
        pending = db.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE state IN ('queued','running')"
        ).fetchone()["n"]
        if pending >= settings.max_jobs:
            raise HTTPException(503, "Processing is at capacity; try later")
    pid = uuid4().hex
    owner = secrets.token_urlsafe(48)
    folder = settings.data_dir / "projects" / pid
    images = folder / "images"
    images.mkdir(parents=True, exist_ok=False)
    saved = []
    total = 0
    hashes: set[str] = set()
    try:
        for i, upload in enumerate(photos):
            data = await upload.read(MAX_FILE_BYTES + 1)
            await upload.close()
            if len(data) > MAX_FILE_BYTES:
                raise HTTPException(413, "Photograph exceeds 12 MB")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise HTTPException(413, "Combined photo size is too large")
            clean, w, h, digest = decode_photo(data, upload.content_type)
            if digest in hashes:
                raise HTTPException(422, "Duplicate photographs detected; upload different angles")
            hashes.add(digest)
            photo_id = uuid4().hex
            path = images / f"{i+1:03d}.jpg"
            path.write_bytes(clean)
            saved.append((photo_id, pid, str(path), digest, w, h))
        now = datetime.now(timezone.utc)
        with connect(settings.data_dir) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO projects(id,token_hash,created_at,expires_at,consent_at) VALUES(?,?,?,?,?)",
                (pid, fingerprint(owner), now.isoformat(),
                 (now + timedelta(days=settings.data_retention_days)).isoformat(), now.isoformat()))
            db.executemany(
                "INSERT INTO photos(id,project_id,path,sha256,width,height) VALUES(?,?,?,?,?,?)", saved)
            db.execute("COMMIT")
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {
        "project_id": pid, "project_token": owner,
        "image_count": len(saved), "expires_at": (now + timedelta(days=settings.data_retention_days)).isoformat(),
        "status": "received",
    }


class ReconstructionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_height_mm: Literal[80, 100, 120, 150] = 100
    quality: Literal["standard", "high"] = "standard"


class ProductionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["review_required", "needs_repair", "geometry_reviewed",
                    "supplier_accepted", "printed", "shipped", "rejected"]


@app.post("/api/v2/projects/{pid}/reconstruct", status_code=202)
def reconstruct(pid: str, body: ReconstructionRequest,
                token: str | None = Depends(owner_token)):
    authorize(pid, token)
    if not shutil.which(settings.colmap) or not shutil.which(settings.blender):
        raise HTTPException(503, "3D reconstruction binaries are not installed on this server")
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        active = db.execute("SELECT COUNT(*) AS n FROM jobs WHERE project_id=? AND state IN ('queued','running')", (pid,)).fetchone()["n"]
        count = db.execute("SELECT COUNT(*) AS n FROM jobs WHERE project_id=?", (pid,)).fetchone()["n"]
        pending = db.execute("SELECT COUNT(*) AS n FROM jobs WHERE state IN ('queued','running')").fetchone()["n"]
        if active or count >= 3 or pending >= settings.max_jobs:
            db.execute("ROLLBACK")
            raise HTTPException(409, "Processing limit reached or job already running")
        jid, vid = uuid4().hex, uuid4().hex
        db.execute(
            "INSERT INTO jobs(id,project_id,version_id,state,stage,target_height_mm,quality,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (jid, pid, vid, "queued", "awaiting_worker", body.target_height_mm, body.quality, utc(), utc()))
        db.execute("COMMIT")
    return {"job_id": jid, "version_id": vid, "status": "queued"}


@app.get("/api/v2/projects/{pid}")
def project_details(pid: str, token: str | None = Depends(owner_token)):
    row = authorize(pid, token)
    with connect(settings.data_dir) as db:
        jobs = db.execute("SELECT id,version_id,state,stage,error,created_at FROM jobs WHERE project_id=? ORDER BY created_at DESC", (pid,)).fetchall()
        versions = db.execute("SELECT id,created_at,customer_approved,operator_status FROM versions WHERE project_id=? ORDER BY created_at DESC", (pid,)).fetchall()
        images = db.execute("SELECT COUNT(*) AS n FROM photos WHERE project_id=?", (pid,)).fetchone()["n"]
    return {"project_id": pid, "image_count": images, "expires_at": row["expires_at"],
            "jobs": [dict(j) for j in jobs], "versions": [dict(v) for v in versions]}


@app.get("/api/v2/projects/{pid}/jobs/{jid}")
def job_status(pid: str, jid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    with connect(settings.data_dir) as db:
        job = db.execute(
            "SELECT id,version_id,state,stage,error,created_at FROM jobs WHERE id=? AND project_id=?",
            (jid, pid)).fetchone()
    if not job:
        raise HTTPException(404, "Job not found")
    return dict(job)


def get_version(pid: str, vid: str):
    with connect(settings.data_dir) as db:
        row = db.execute("SELECT * FROM versions WHERE id=? AND project_id=?", (vid, pid)).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    return row


@app.get("/api/v2/projects/{pid}/versions/{vid}/preview")
def preview(pid: str, vid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    version = get_version(pid, vid)
    return FileResponse(artifact_path(version["preview_path"]), media_type="model/gltf-binary",
                        headers={"Content-Disposition":"inline; filename=replica.glb"})


@app.get("/api/v2/projects/{pid}/versions/{vid}/report")
def report(pid: str, vid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    version = get_version(pid, vid)
    return FileResponse(artifact_path(version["report_path"]), media_type="application/json",
                        headers={"Content-Disposition":"inline; filename=qa-report.json"})


@app.post("/api/v2/projects/{pid}/versions/{vid}/approve")
def approve(pid: str, vid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    get_version(pid, vid)
    with connect(settings.data_dir) as db:
        db.execute("UPDATE versions SET customer_approved=1 WHERE id=? AND project_id=?", (vid, pid))
    return {"version_id": vid, "status": "design_approved_unpaid"}


@app.get("/api/v2/projects/{pid}/versions/{vid}/package")
def download(pid: str, vid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    version = get_version(pid, vid)
    if not version["customer_approved"]:
        raise HTTPException(409, "Approve the real reconstruction before download")
    return FileResponse(artifact_path(version["package_path"]), media_type="application/zip",
                        filename=f"minimo-realistic-{vid}.zip")


@app.delete("/api/v2/projects/{pid}", status_code=204)
def delete_project(pid: str, token: str | None = Depends(owner_token)):
    authorize(pid, token)
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        active = db.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE project_id=? AND state IN ('queued','running')", (pid,)
        ).fetchone()["n"]
        if active:
            db.execute("ROLLBACK")
            raise HTTPException(409, "A reconstruction is running; delete after completion")
        db.execute("DELETE FROM projects WHERE id=?", (pid,))
        db.execute("COMMIT")
    shutil.rmtree(settings.data_dir / "projects" / pid, ignore_errors=True)
    return Response(status_code=204)


@app.get("/api/v2/admin/queue", dependencies=[Depends(require_admin)])
def admin_queue():
    with connect(settings.data_dir) as db:
        jobs = db.execute("SELECT id,project_id,version_id,state,stage,created_at FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
        versions = db.execute("SELECT id,project_id,customer_approved,operator_status,created_at FROM versions ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"jobs": [dict(j) for j in jobs], "versions": [dict(v) for v in versions]}


@app.get("/api/v2/admin/versions/{vid}/package", dependencies=[Depends(require_admin)])
def admin_package(vid: str):
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT package_path FROM versions WHERE id=?", (vid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Version not found")
    return FileResponse(artifact_path(row["package_path"]), media_type="application/zip",
                        filename=f"minimo-operator-{vid}.zip")


@app.patch("/api/v2/admin/versions/{vid}", dependencies=[Depends(require_admin)])
def admin_update(vid: str, body: ProductionUpdate):
    transitions = {
        "review_required": {"needs_repair", "geometry_reviewed", "rejected"},
        "needs_repair": {"geometry_reviewed", "rejected"},
        "geometry_reviewed": {"needs_repair", "supplier_accepted", "rejected"},
        "supplier_accepted": {"printed", "rejected"},
        "printed": {"shipped"},
        "shipped": set(), "rejected": set(),
    }
    with connect(settings.data_dir) as db:
        row = db.execute("SELECT operator_status FROM versions WHERE id=?", (vid,)).fetchone()
        if row is None:
            raise HTTPException(404, "Version not found")
        if body.status not in transitions[row["operator_status"]]:
            raise HTTPException(409, "Invalid operator state transition")
        db.execute("UPDATE versions SET operator_status=? WHERE id=?", (body.status, vid))
    return {"version_id": vid, "operator_status": body.status}
