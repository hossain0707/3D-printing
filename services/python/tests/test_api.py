"""API tests use synthetic photos and mocked reconstruction IO; they do not prove GPU/print fidelity."""
import importlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

os.environ["MINIMO_ENV"]="development"
os.environ["MINIMO_DATA_DIR"]=tempfile.mkdtemp(prefix="minimo-real-test-")
os.environ["MINIMO_ENABLE_UPLOADS"]="true"
os.environ["MINIMO_ADMIN_KEY"]="test-operator-secret-"+"a"*32
os.environ["MINIMO_TOKEN_PEPPER"]="test-photo-hmac-secret-"+"z"*32

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

api_module=importlib.import_module("minimo.app")
worker_module=importlib.import_module("minimo.worker")
client=TestClient(api_module.app)


@pytest.fixture(autouse=True)
def reset_rate():
    api_module.RATE.clear()
    with api_module.connect(api_module.settings.data_dir) as db:
        db.execute(
            "INSERT INTO worker_heartbeat(id,last_seen,colmap_available,blender_available) VALUES(1,?,1,1) "
            "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,colmap_available=1,blender_available=1",
            (api_module.utc(),)
        )


def shots(count=12):
    result=[]
    for index in range(count):
        im=Image.new("RGB",(480,640),(100+index*3,140,180))
        draw=ImageDraw.Draw(im)
        draw.ellipse((30+index*2,150,350,500),fill=(190,130+index,98))
        buf=io.BytesIO();im.save(buf,"JPEG",quality=90)
        result.append(("photos",(f"angle-{index:02d}.jpg",buf.getvalue(),"image/jpeg")))
    return result


def create():
    response=client.post("/api/v2/projects",data={"consent":"true"},files=shots())
    assert response.status_code==201,response.text
    return response.json()


def owner(p):
    return {"X-Project-Token":p["project_token"]}


def test_health_is_explicit_not_commercial():
    data=client.get("/api/v2/health").json()
    assert data["pipeline"]=="real_multi_view_photogrammetry"
    assert data["min_photos"]==12
    assert data["payment_enabled"] is False
    assert data["printer_certified"] is False


def test_photo_guards():
    response=client.post("/api/v2/projects",data={"consent":"true"},files=shots(6))
    assert response.status_code==422
    response=client.post("/api/v2/projects",data={"consent":"false"},files=shots())
    assert response.status_code==422
    photo=shots(1)[0]
    response=client.post("/api/v2/projects",data={"consent":"true"},files=[photo]*12)
    assert response.status_code==422
    assert "Duplicate" in response.text
    bad=[("photos",(f"angle-{i}.jpg",b"not a jpeg","image/jpeg")) for i in range(12)]
    assert client.post("/api/v2/projects",data={"consent":"true"},files=bad).status_code==422


def test_private_project_worker_api(monkeypatch):
    project=create()
    pid=project["project_id"]
    url=f"/api/v2/projects/{pid}"
    assert project["image_count"]==12
    assert client.get(url).status_code==401
    assert client.get(url,headers={"X-Project-Token":"other-token"}).status_code==404
    assert client.get(url,headers=owner(project)).json()["image_count"]==12

    # Real processing must fail closed if COLMAP and Blender are unavailable.
    with api_module.connect(api_module.settings.data_dir) as db:
        db.execute("UPDATE worker_heartbeat SET last_seen=? WHERE id=1", ("2020-01-01T00:00:00+00:00",))
    denied=client.post(url+"/reconstruct",json={"target_height_mm":100},headers=owner(project))
    assert denied.status_code==503

    # Unit tests mock ONLY the external GPU worker output.
    # No synthetic geometry is shipped as an actual application result.
    with api_module.connect(api_module.settings.data_dir) as db:
        db.execute("UPDATE worker_heartbeat SET last_seen=? WHERE id=1",(api_module.utc(),))
    started=client.post(url+"/reconstruct",json={"target_height_mm":100},headers=owner(project))
    assert started.status_code==202,started.text
    job=started.json()
    jid=job["job_id"];vid=job["version_id"]
    assert client.get(url+"/jobs/"+jid,headers=owner(project)).json()["state"]=="queued"
    conflict=client.post(url+"/reconstruct",json={},headers=owner(project))
    assert conflict.status_code==409

    def mocked_gpu_reconstruction(folder,job_id,version_id,height,quality,settings,stage):
        assert len(list((folder/"images").glob("*.jpg")))==12
        stage("real_gpu_process_test_double")
        delivery=folder/"versions"/version_id
        delivery.mkdir(parents=True)
        preview=delivery/"preview.glb";preview.write_bytes(b"glTF"+b"0"*1024)
        report=delivery/"qa-report.json";report.write_text(json.dumps({"status":"REVIEW_REQUIRED"}))
        package=delivery/"print-candidate.zip"
        with zipfile.ZipFile(package,"w") as z:
            z.writestr("README-BEFORE-PRINTING.txt","Test double only")
        return {"preview_path":str(preview.relative_to(settings.data_dir)),
                "package_path":str(package.relative_to(settings.data_dir)),
                "report_path":str(report.relative_to(settings.data_dir))}

    monkeypatch.setattr(worker_module,"run_reconstruction",mocked_gpu_reconstruction)
    assert worker_module.process_next(api_module.settings) is True
    done=client.get(url+"/jobs/"+jid,headers=owner(project)).json()
    assert done["state"]=="completed"
    assert client.get(url+"/versions/"+vid+"/preview",headers=owner(project)).status_code==200
    assert client.get(url+"/versions/"+vid+"/report",headers=owner(project)).json()["status"]=="REVIEW_REQUIRED"
    assert client.get(url+"/versions/"+vid+"/package",headers=owner(project)).status_code==409

    assert client.post(url+"/versions/"+vid+"/approve",headers=owner(project)).status_code==200
    assert client.get(url+"/versions/"+vid+"/package",headers=owner(project)).status_code==200
    assert client.get(url+"/versions/"+vid+"/package",headers={"X-Project-Token":"wrong"}).status_code==404

    assert client.get("/api/v2/admin/queue").status_code==401
    admin={"X-Admin-Key":os.environ["MINIMO_ADMIN_KEY"]}
    queue=client.get("/api/v2/admin/queue",headers=admin)
    assert queue.status_code==200 and queue.json()["versions"]
    assert client.patch("/api/v2/admin/versions/"+vid,headers=admin,json={"status":"geometry_reviewed"}).status_code==200
    assert client.patch("/api/v2/admin/versions/"+vid,headers=admin,json={"status":"shipped"}).status_code==409
    assert client.get("/api/v2/admin/versions/"+vid+"/package",headers=admin).status_code==200

    assert client.delete(url,headers=owner(project)).status_code==204
    assert client.get(url,headers=owner(project)).status_code==404
    assert not (api_module.settings.data_dir/"projects"/pid).exists()


def test_job_validation():
    project=create()
    path=f"/api/v2/projects/{project['project_id']}/reconstruct"
    assert client.post(path,headers=owner(project),json={"quality":"impossible"}).status_code==422
    assert client.post(path,headers=owner(project),json={"target_height_mm":13}).status_code==422
