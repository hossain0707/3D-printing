"""MINIMO REAL processing-host preflight. Never reports a completed scan."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

from .settings import Settings


def _check_command(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        proc=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            text=True,errors="replace",timeout=timeout,check=False)
        return proc.returncode == 0, proc.stdout[-6000:]
    except (OSError,subprocess.TimeoutExpired) as error:
        return False,str(error)


def inspect(settings: Settings) -> dict:
    """Only verify software/driver readiness. An actual multi-photo test is mandatory."""
    checks={}
    colmap=shutil.which(settings.colmap)
    blender=shutil.which(settings.blender)
    nvidia=shutil.which("nvidia-smi")
    checks["colmap_installed"]=bool(colmap)
    checks["blender_installed"]=bool(blender)
    checks["nvidia_driver_visible"]=bool(nvidia)
    if colmap:
        _,out=_check_command([colmap,"feature_extractor","-h"])
        checks["colmap_current_feature_flags"]="FeatureExtraction.use_gpu" in out
        _,dense=_check_command([colmap,"patch_match_stereo","-h"])
        checks["colmap_dense_command"]="PatchMatchStereo" in dense or "patch_match_stereo" in dense
    else:
        checks["colmap_current_feature_flags"]=False
        checks["colmap_dense_command"]=False
    if blender:
        ok,out=_check_command([
            blender,"--background","--factory-startup","--python-exit-code","17",
            "--python-expr","import bpy; assert hasattr(bpy.ops.wm,'obj_import'); "
                            "assert hasattr(bpy.ops.wm,'obj_export'); "
                            "assert hasattr(bpy.ops.export_scene,'gltf')"
        ],timeout=40)
        checks["blender_obj_and_glb_operators"]=ok
    else:
        checks["blender_obj_and_glb_operators"]=False
    if nvidia:
        ok,out=_check_command([nvidia,"--query-gpu=name,memory.total",
                              "--format=csv,noheader"],timeout=10)
        checks["nvidia_gpu_query"]=bool(ok and out.strip())
        gpu_summary=out.splitlines()[:5] if ok else []
    else:
        checks["nvidia_gpu_query"]=False
        gpu_summary=[]
    total,used,free=shutil.disk_usage(settings.data_dir)
    checks["storage_over_10gb_free"]=free >= 10*1024**3
    mandatory=["colmap_installed","blender_installed","nvidia_driver_visible",
               "colmap_current_feature_flags","colmap_dense_command",
               "blender_obj_and_glb_operators","nvidia_gpu_query"]
    ready=all(checks[key] for key in mandatory)
    return {
        "processing_host_ready_for_pilot":ready,
        "checks":checks,
        "gpu_summary":gpu_summary,
        "storage_free_gb":round(free/1024**3,1),
        "warning":"CUDA dense reconstruction and photorealistic accuracy still require an actual scan. This is not print certification."
    }


def main():
    settings=Settings.load()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    status=inspect(settings)
    print(json.dumps(status,indent=2))
    if not status["processing_host_ready_for_pilot"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
