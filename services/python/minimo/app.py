"""MINIMO Studio FastAPI API: privacy-aware, durable, CPU-first production foundation.

The API is intentionally NOT a complete ecommerce system. Payment, shipping and
supplier certification have separate integration gates.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
from typing import Annotated, Literal

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from .db import connect, initialize
from .settings import Settings

settings = Settings.load()
initialize(settings.data_dir)
app = FastAPI(
    title="MINIMO Python Generator API",
    version="1.0.0",
    description="CPU-friendly chibi design jobs, approval and private manufacturing handoff.",
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Project-Token", "X-Admin-Key"],
    max_age=3600,
)

MAX_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 16_000_000
_UPLOAD_GATE: defaultdict[str, deque[float]] = defaultdict(deque)
_GATE_LOCK = Lock()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_digest(token: str) -> str:
    return hmac.new(settings.token_pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def get_project(project_id: str, token: str | None) -> sqlite3.Row:
    if not token:
        raise HTTPException(401, "Missing project token")
    with connect(settings.data_dir) as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if row is None or not hmac.compare_digest(row["token_hash"], token_digest(token)):
        raise HTTPException(404, "Project not found")
    return row


def owner_token(x_project_token: Annotated[str | None, Header()] = None) -> str | None:
    return x_project_token


def admin_auth(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not settings.admin_key:
        raise HTTPException(503, "Admin authentication is not configured")
    if not x_admin_key or not hmac.compare_digest(settings.admin_key, x_admin_key):
        raise HTTPException(401, "Unauthorized")


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: Literal["classic", "dreamy", "collector"] = "classic"
    hair: Literal["short", "medium", "long", "bun"] = "short"
    pose: Literal["stand", "wave", "hug"] = "wave"
    size_mm: Literal[50, 80, 100] = 80
    seed: int = Field(default=11, ge=0, le=2_147_483_647)
    inscription: str = Field(default="", max_length=18)
    colors: dict[Literal["skin", "hair", "top", "bottom"], str] = Field(default_factory=dict)

    def model_post_init(self, __context):
        for value in self.colors.values():
            if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
                raise ValueError("Color must be #RRGGBB")


class ProductionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["unreviewed", "needs_repair", "validated", "submitted", "printed", "shipped", "rejected"]


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "engine": "python-trimesh-cpu",
        "generation_enabled": settings.public_generation,
        "manufacturing_certified": False,
        "payment_enabled": False,
    }


def throttle(ip: str, max_events: int = 12, window_s: int = 3600) -> None:
    now = time.monotonic()
    with _GATE_LOCK:
        events = _UPLOAD_GATE[ip]
        while events and events[0] < now - window_s:
            events.popleft()
        if len(events) >= max_events:
            raise HTTPException(429, "Rate limit reached")
        events.append(now)


@app.post("/api/v1/projects", status_code=201)
async def create_project(request: Request, photo: UploadFile = File(...)):
    if not settings.public_generation:
        raise HTTPException(503, "Public processing is disabled until an operator enables it")
    throttle(request.client.host if request.client else "unknown")
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Only JPEG, PNG or WebP images are supported")
    raw = await photo.read(MAX_BYTES + 1)
    await photo.close()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Image exceeds 8 MB")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(415, "Unsupported image format")
            image.load()
            safe = ImageOps.exif_transpose(image).convert("RGB")
            safe.thumbnail((2048, 2048))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid or unsafe image")
    project_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    photo_path = settings.data_dir / "images" / (project_id + ".jpg")
    safe.save(photo_path, "JPEG", quality=88, optimize=True)
    with connect(settings.data_dir) as db:
        db.execute("INSERT INTO projects(id,token_hash,source_path,created_at) VALUES(?,?,?,?)",
                   (project_id, token_digest(token), str(photo_path), utc()))
    return {"project_id": project_id, "project_token": token, "status": "created",
            "privacy": "Photo stored privately on configured service disk; not in public GitHub/Vercel"}


@app.post("/api/v1/projects/{project_id}/generate", status_code=202)
def submit_generation(project_id: str, body: GenerateRequest,
                      token: str | None = Depends(owner_token)):
    get_project(project_id, token)
    with connect(settings.data_dir) as db:
        active = db.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE project_id=? AND state IN ('queued','running')",
            (project_id,)).fetchone()["n"]
        count = db.execute("SELECT COUNT(*) AS n FROM jobs WHERE project_id=?", (project_id,)).fetchone()["n"]
        if active >= 1:
            raise HTTPException(409, "Wait for the current generation to finish")
        if count >= 12:
            raise HTTPException(429, "This project has reached its generation limit")
        job_id, version_id, timestamp = str(uuid4()), str(uuid4()), utc()
        db.execute(
            "INSERT INTO jobs(id,project_id,state,params_json,version_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (job_id, project_id, "queued", body.model_dump_json(), version_id, timestamp, timestamp))
    return {"job_id": job_id, "version_id": version_id, "status": "queued"}


@app.get("/api/v1/projects/{project_id}/jobs/{job_id}")
def job_status(project_id: str, job_id: str, token: str | None = Depends(owner_token)):
    get_project(project_id, token)
    with connect(settings.data_dir) as db:
        job = db.execute("SELECT * FROM jobs WHERE project_id=? AND id=?", (project_id,job_id)).fetchone()
    if not job:
        raise HTTPException(404, "Job not found")
    return {"job_id": job_id, "version_id":job["version_id"], "status":job["state"],
            "error": job["error"] if job["state"] == "failed" else None}


@app.get("/api/v1/projects/{project_id}/versions/{version_id}/preview")
def preview(project_id: str, version_id: str, token: str | None = Depends(owner_token)):
    get_project(project_id, token)
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT * FROM versions WHERE project_id=? AND id=?",(project_id,version_id)).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    import zipfile
    with zipfile.ZipFile(row["zip_path"]) as archive:
        content=archive.read("preview/approved-character.glb")
    return Response(content=content, media_type="model/gltf-binary",
                    headers={"Content-Disposition":"inline; filename=character.glb"})


@app.post("/api/v1/projects/{project_id}/versions/{version_id}/approve")
def approve(project_id: str, version_id: str, token: str | None = Depends(owner_token)):
    get_project(project_id, token)
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT id FROM versions WHERE project_id=? AND id=?",(project_id,version_id)).fetchone()
        if not row:
            raise HTTPException(404, "Version not found")
        db.execute("UPDATE projects SET approved_version=? WHERE id=?",(version_id,project_id))
    return {"approved_version_id":version_id, "status":"design_approved_not_paid"}


@app.get("/api/v1/projects/{project_id}/versions/{version_id}/package")
def package(project_id: str, version_id: str, token: str | None = Depends(owner_token)):
    project = get_project(project_id, token)
    if project["approved_version"] != version_id:
        raise HTTPException(409, "Approve this version before downloading")
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT zip_path FROM versions WHERE project_id=? AND id=?",
                       (project_id,version_id)).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    return FileResponse(row["zip_path"], media_type="application/zip",
                        filename="minimo-print-candidate-"+version_id+".zip")


@app.get("/api/v1/admin/queue", dependencies=[Depends(admin_auth)])
def admin_queue():
    with connect(settings.data_dir) as db:
        jobs=db.execute("SELECT id,project_id,state,version_id,error,created_at FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
        versions=db.execute("""SELECT v.id,v.project_id,v.production_state,v.created_at,
          CASE WHEN p.approved_version = v.id THEN 1 ELSE 0 END AS customer_approved
          FROM versions v JOIN projects p ON p.id=v.project_id
          ORDER BY v.created_at DESC LIMIT 100""").fetchall()
    return {"jobs":[dict(x) for x in jobs],"versions":[dict(x) for x in versions]}


@app.patch("/api/v1/admin/versions/{version_id}/production", dependencies=[Depends(admin_auth)])
def update_production(version_id: str, body: ProductionUpdate):
    # Operator attestation only. No automatic printer guarantees or payment state changes.
    allowed = {
        "unreviewed":{"needs_repair","rejected","validated"},
        "needs_repair":{"validated","rejected"},
        "validated":{"needs_repair","submitted","rejected"},
        "submitted":{"printed","rejected"},
        "printed":{"shipped"},
        "shipped":set(),
        "rejected":set(),
    }
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT production_state FROM versions WHERE id=?",(version_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Version not found")
        if body.status not in allowed[row["production_state"]]:
            raise HTTPException(409, "Invalid production transition")
        db.execute("UPDATE versions SET production_state=? WHERE id=?",(body.status,version_id))
    return {"version_id": version_id, "production_status": body.status}


@app.get("/api/v1/admin/versions/{version_id}/package", dependencies=[Depends(admin_auth)])
def admin_package(version_id: str):
    with connect(settings.data_dir) as db:
        row=db.execute("SELECT zip_path FROM versions WHERE id=?",(version_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Version not found")
    return FileResponse(row["zip_path"], filename="minimo-operator-"+version_id+".zip",
                        media_type="application/zip")


@app.get("/api/v1/projects/{project_id}")
def project_details(project_id: str, token: str | None = Depends(owner_token)):
    project=get_project(project_id,token)
    with connect(settings.data_dir) as db:
        versions=db.execute("SELECT id,created_at,production_state FROM versions WHERE project_id=? ORDER BY created_at DESC LIMIT 20",
                            (project_id,)).fetchall()
    return {"project_id":project_id,"approved_version_id":project["approved_version"],
            "versions":[dict(x) for x in versions],
            "customer_payment":"NOT_COLLECTED"}


@app.delete("/api/v1/projects/{project_id}", status_code=204)
def delete_project(project_id: str, token: str | None = Depends(owner_token)):
    project=get_project(project_id,token)
    paths=[]
    with connect(settings.data_dir) as db:
        db.execute("BEGIN IMMEDIATE")
        active=db.execute("SELECT COUNT(*) AS n FROM jobs WHERE project_id=? AND state IN ('queued','running')",
                          (project_id,)).fetchone()["n"]
        if active:
            db.execute("ROLLBACK")
            raise HTTPException(409,"Cannot delete while a generation job is running")
        paths=[Path(row["zip_path"]) for row in db.execute("SELECT zip_path FROM versions WHERE project_id=?",(project_id,))]
        paths.append(Path(project["source_path"]))
        db.execute("DELETE FROM versions WHERE project_id=?",(project_id,))
        db.execute("DELETE FROM jobs WHERE project_id=?",(project_id,))
        db.execute("DELETE FROM projects WHERE id=?",(project_id,))
        db.execute("COMMIT")
    for path in paths:
        try:
            if path.resolve().is_relative_to(settings.data_dir.resolve()):
                path.unlink(missing_ok=True)
        except OSError:
            # Background backup retention must be separately covered in privacy policy.
            pass
    return Response(status_code=204)
