"""Integration tests for the private Python design API and durable CPU worker."""
import io
import os
import tempfile
import zipfile
from pathlib import Path

os.environ["MINIMO_ENV"] = "development"
os.environ["MINIMO_PUBLIC_GENERATION"] = "true"
os.environ["MINIMO_DATA_DIR"] = tempfile.mkdtemp(prefix="minimo-test-")
os.environ["MINIMO_ADMIN_KEY"] = "test-admin-key-"+("x"*32)

from fastapi.testclient import TestClient
from PIL import Image
from minimo.app import app, settings
from minimo.worker import process_next

client = TestClient(app)


def new_image():
    b = io.BytesIO()
    im = Image.new("RGB", (192, 256), (207, 155, 130))
    im.save(b, "PNG")
    return b.getvalue()


def new_project():
    response = client.post("/api/v1/projects",
        files={"photo":("portrait.png",new_image(),"image/png")})
    assert response.status_code == 201, response.text
    return response.json()


def test_health_does_not_claim_commercial_readiness():
    info = client.get("/api/v1/health").json()
    assert info["status"] == "ok"
    assert info["payment_enabled"] is False
    assert info["manufacturing_certified"] is False


def test_rejects_invalid_media():
    response = client.post("/api/v1/projects",
        files={"photo":("bad.txt",b"not an image","text/plain")})
    assert response.status_code == 415


def test_private_generation_approval_and_export():
    project = new_project()
    pid, token = project["project_id"], project["project_token"]
    url = f"/api/v1/projects/{pid}"
    unauthorized = client.post(url+"/generate",json={"style":"classic"})
    assert unauthorized.status_code == 401

    headers = {"X-Project-Token":token}
    submit = client.post(url+"/generate",headers=headers,json={
        "style":"dreamy","hair":"long","pose":"wave","size_mm":80,
        "colors":{"top":"#ea7f89"},"seed":123
    })
    assert submit.status_code == 202, submit.text
    job = submit.json()
    assert client.get(url+"/jobs/"+job["job_id"],headers=headers).json()["status"] == "queued"

    assert process_next(settings) is True
    assert client.get(url+"/jobs/"+job["job_id"],headers=headers).json()["status"] == "completed"
    vid = job["version_id"]
    preview = client.get(url+f"/versions/{vid}/preview",headers=headers)
    assert preview.status_code == 200
    assert preview.content[:4] == b"glTF"

    not_approved = client.get(url+f"/versions/{vid}/package",headers=headers)
    assert not_approved.status_code == 409
    approved = client.post(url+f"/versions/{vid}/approve",headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "design_approved_not_paid"

    package=client.get(url+f"/versions/{vid}/package",headers=headers)
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        names=archive.namelist()
        assert "preview/approved-character.glb" in names
        assert "print-candidate/miniature.obj" in names
        assert "print-candidate/miniature.mtl" in names
        assert "ORDER-MANIFEST.json" in names
        assert any(name.endswith(".png") for name in names)
        assert b"mtllib miniature.mtl" in archive.read("print-candidate/miniature.obj")

    private = client.get(url+f"/versions/{vid}/package",headers={"X-Project-Token":"wrong"})
    assert private.status_code == 404

    denied = client.get("/api/v1/admin/queue")
    assert denied.status_code == 401
    admin = client.get("/api/v1/admin/queue",headers={"X-Admin-Key":os.environ["MINIMO_ADMIN_KEY"]})
    assert admin.status_code == 200
    assert admin.json()["versions"]


def test_validation_and_unsafe_changes():
    project=new_project()
    url=f"/api/v1/projects/{project['project_id']}/generate"
    head={"X-Project-Token":project["project_token"]}
    assert client.post(url,headers=head,json={"size_mm":72}).status_code == 422
    assert client.post(url,headers=head,json={"colors":{"top":"red"}}).status_code == 422
    assert client.post(url,headers=head,json={"style":"unknown"}).status_code == 422
