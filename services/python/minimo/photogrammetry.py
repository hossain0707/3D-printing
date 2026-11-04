"""Real COLMAP photogrammetry from overlapping photographs; never fabricate a mesh."""
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path


class ReconstructionError(Exception):
    pass


def run_cli(binary, args, cwd, logfile, timeout):
    env=os.environ.copy()
    env["QT_QPA_PLATFORM"]="offscreen"
    env.setdefault("OMP_NUM_THREADS","4")
    with logfile.open("a",encoding="utf-8") as log:
        log.write("\nRUN: "+Path(binary).name+" "+str(args[:2])+"\n")
        log.flush()
        try:
            proc=subprocess.run([binary,*args],cwd=cwd,env=env,stdout=log,
                                stderr=subprocess.STDOUT,timeout=timeout,check=False)
        except FileNotFoundError as exc:
            raise ReconstructionError(f"Executable unavailable: {Path(binary).name}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ReconstructionError(f"Processing exceeded timeout: {Path(binary).name}") from exc
    if proc.returncode:
        raise ReconstructionError(f"Command {Path(binary).name} failed with exit code {proc.returncode}")


def require(path, minimum=100):
    if not path.is_file() or path.stat().st_size < minimum:
        raise ReconstructionError("Missing or invalid generated artifact: "+path.name)
    return path


def run_reconstruction(folder, job_id, version_id, height_mm, quality, settings, stage):
    """Run actual SfM -> dense MVS -> meshing -> photograph textures -> Blender export.

    Dense COLMAP PatchMatch requires a CUDA-capable COLMAP installation.
    """
    colmap=shutil.which(settings.colmap)
    blender=shutil.which(settings.blender)
    if not colmap or not blender:
        raise ReconstructionError("COLMAP and Blender must be installed")
    images=sorted((folder/"images").glob("*.jpg"))
    if len(images)<12:
        raise ReconstructionError("At least 12 photos required")
    work=folder/"jobs"/job_id
    photos=work/"images";photos.mkdir(parents=True,exist_ok=False)
    for src in images:
        shutil.copy2(src,photos/src.name)
    sparse=work/"sparse";sparse.mkdir()
    dense=work/"dense";dense.mkdir()
    db=work/"database.db";log=work/"pipeline.log"
    def run(step,app,*args):
        stage(step)
        run_cli(app,list(args),work,log,settings.stage_timeout_seconds)

    run("extracting_features",colmap,"feature_extractor",
        "--database_path",str(db),"--image_path",str(photos),
        "--FeatureExtraction.use_gpu","0")
    require(db,256)
    run("matching_photographs",colmap,"exhaustive_matcher",
        "--database_path",str(db),"--FeatureMatching.use_gpu","0")
    run("mapping_cameras",colmap,"mapper",
        "--database_path",str(db),"--image_path",str(photos),"--output_path",str(sparse))
    models=sorted([d for d in sparse.iterdir()
                   if d.is_dir() and ((d/"cameras.bin").exists() or (d/"cameras.txt").exists())])
    if not models:
        raise ReconstructionError("Could not register enough overlapping photographs")
    run("undistorting_images",colmap,"image_undistorter",
        "--image_path",str(photos),"--input_path",str(models[0]),
        "--output_path",str(dense),"--output_type","COLMAP",
        "--max_image_size","2600" if quality=="high" else "1800")
    run("dense_reconstruction",colmap,"patch_match_stereo",
        "--workspace_path",str(dense),"--workspace_format","COLMAP",
        "--PatchMatchStereo.geom_consistency","true")
    fused=dense/"fused.ply"
    run("fusing_depth",colmap,"stereo_fusion",
        "--workspace_path",str(dense),"--workspace_format","COLMAP",
        "--input_type","geometric","--output_path",str(fused))
    require(fused,1024)
    meshed=dense/"meshed-poisson.ply"
    run("building_surface",colmap,"poisson_mesher","--input_path",str(fused),
        "--output_path",str(meshed))
    require(meshed,1024)
    textured=dense/"textured"
    run("projecting_photo_textures",colmap,"mesh_texturer",
        "--workspace_path",str(dense),"--input_path",str(meshed),
        "--output_path",str(textured))
    objs=list(textured.rglob("*.obj")) if textured.exists() else []
    if not objs:
        objs=list(dense.glob("textured*.obj"))
    if not objs:
        raise ReconstructionError("COLMAP did not produce textured geometry")
    obj=max(objs,key=lambda p:p.stat().st_size)
    require(obj,1024)
    if not list(obj.parent.glob("*.mtl")) or not (
        list(obj.parent.glob("*.png"))+list(obj.parent.glob("*.jpg"))
    ):
        raise ReconstructionError("No photo-derived texture atlas produced")
    delivery=folder/"versions"/version_id
    delivery.mkdir(parents=True,exist_ok=False)
    preview=delivery/"preview.glb"
    printable=delivery/"print"
    report=delivery/"qa-report.json"
    blender_script=Path(__file__).resolve().parents[3]/"tools"/"blender"/"prepare_realistic.py"
    if not blender_script.exists():
        raise ReconstructionError("Blender processing script unavailable")
    run("normalizing_scale_and_exporting",blender,
        "--background","--factory-startup","--python",str(blender_script),
        "--",str(obj),str(preview),str(printable),str(height_mm),str(report))
    require(preview,1024);require(report,100)
    if not (list(printable.glob("*.obj")) and list(printable.glob("*.mtl")) and
            (list(printable.glob("*.png"))+list(printable.glob("*.jpg")))):
        raise ReconstructionError("Incomplete UV/textured print package")
    qa=json.loads(report.read_text(encoding="utf-8"))
    if qa.get("status")!="REVIEW_REQUIRED":
        raise ReconstructionError("Manufacturing report is invalid")
    stage("packaging")
    package=delivery/"print-candidate.zip"
    with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED,compresslevel=5) as zipf:
        zipf.write(preview,"preview/reconstruction.glb")
        zipf.write(report,"qa-report.json")
        for asset in printable.iterdir():
            if asset.is_file():
                zipf.write(asset,"print-candidate/"+asset.name)
        zipf.writestr("READ-BEFORE-PRINTING.txt",
           "This is a real multi-photo reconstruction, but it is NOT certified printer-ready.\n"
           "Check geometry, manifoldness, scale, thin features, UV textures, "
           "face likeness and color with a supplier.\n"
           "Without a scale marker the reconstruction's absolute size is unknown. "
           "Automatic sizing uses the longest axis as the intended height.\n")
    require(package,1024)
    return {"preview_path":str(preview),"package_path":str(package),
            "report_path":str(report),"photo_count":len(images)}
