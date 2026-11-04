"""Convert actual COLMAP photo-textured OBJ to WebGL preview and metric print candidate.

This script must run inside Blender (4.4+). It never creates fictional geometry.
It does not certify a print. Arbitrary SfM orientation/scale needs operator QA.
"""
import json
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector


def world_bounds(meshes):
    coords=[o.matrix_world@Vector(corner) for o in meshes for corner in o.bound_box]
    if not coords:
        raise RuntimeError("No mesh coordinates")
    mins=Vector((min(c[i] for c in coords) for i in range(3)))
    maxs=Vector((max(c[i] for c in coords) for i in range(3)))
    return mins,maxs


def main():
    params=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if len(params)!=5:
        raise RuntimeError("Expected: source.obj preview.glb print-dir target-height-mm report.json")
    obj_path, preview_path, print_path, height_raw, qa_path=params
    source=Path(obj_path).resolve()
    preview=Path(preview_path).resolve()
    output=Path(print_path).resolve()
    report=Path(qa_path).resolve()
    height=int(height_raw)
    if height not in (80,100,120,150):
        raise RuntimeError("Unsupported target height")
    if not source.is_file():
        raise RuntimeError("Source OBJ is missing")
    output.mkdir(parents=True,exist_ok=True)
    preview.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(source),forward_axis="Y",up_axis="Z")
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
    if not meshes:
        raise RuntimeError("COLMAP OBJ contains no mesh")
    faces=sum(len(o.data.polygons) for o in meshes)
    if faces<200:
        raise RuntimeError("Reconstruction is too sparse for meaningful realistic output")
    image_nodes=[]
    for obj in meshes:
        if len(obj.data.uv_layers)==0:
            raise RuntimeError("Reconstructed geometry has no UV coordinates")
        for material in obj.data.materials:
            if material and material.use_nodes:
                image_nodes.extend(
                    node for node in material.node_tree.nodes
                    if node.type=="TEX_IMAGE" and node.image is not None
                )
    if not image_nodes:
        raise RuntimeError("No photographic texture images found in imported model")
    for node in image_nodes:
        if not node.image.has_data:
            try: node.image.reload()
            except Exception: pass
        if not node.image.has_data:
            raise RuntimeError("Reconstruction references missing texture image")

    before_min,before_max=world_bounds(meshes)
    size=before_max-before_min
    axis=max(range(3),key=lambda i:size[i])
    if size[axis]<=0:
        raise RuntimeError("Invalid reconstruction dimensions")
    if axis==0:
        rotation=Matrix.Rotation(-1.57079632679,4,"Y")
    elif axis==1:
        rotation=Matrix.Rotation(1.57079632679,4,"X")
    else:
        rotation=Matrix.Identity(4)
    for o in meshes:
        o.matrix_world=rotation@o.matrix_world
    low,high=world_bounds(meshes)
    height_native=high.z-low.z
    if height_native<=0:
        raise RuntimeError("Reconstruction has zero height")
    scale=(height/1000.0)/height_native
    scalar=Matrix.Scale(scale,4)
    for o in meshes:
        o.matrix_world=scalar@o.matrix_world
    low,high=world_bounds(meshes)
    shift=Matrix.Translation(Vector((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z)))
    for o in meshes:
        o.matrix_world=shift@o.matrix_world
    low,high=world_bounds(meshes)

    boundary=0
    nonmanifold=0
    for obj in meshes:
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        boundary+=sum(1 for edge in bm.edges if edge.is_boundary)
        nonmanifold+=sum(1 for edge in bm.edges if not edge.is_manifold)
        bm.free()

    # OpenGL preview uses meters; true dimensions are encoded in geometry.
    bpy.ops.export_scene.gltf(filepath=str(preview),export_format="GLB",
                              export_materials="EXPORT",export_yup=True,
                              export_cameras=False,export_lights=False)

    # Full-color OBJ is exported in millimeters, Z up, with texture sidecars.
    bpy.ops.wm.obj_export(filepath=str(output/"replica.obj"),forward_axis="Y",
                          up_axis="Z",global_scale=1000.0,
                          export_uv=True,export_normals=True,
                          export_materials=True,path_mode="COPY",
                          export_triangulated_mesh=True)

    # Blender's COPY mode may leave sidecars in subfolders. Collecting the
    # complete output directory happens in the worker, preserving paths.
    textures=[p.name for p in output.rglob("*") if p.suffix.lower() in (".png",".jpg",".jpeg")]
    summary={
        "status":"REVIEW_REQUIRED",
        "source":"real_multiview_photo_reconstruction",
        "target_height_mm":height,
        "measured_extent_mm":[round((high[i]-low[i])*1000,2) for i in range(3)],
        "mesh_parts":len(meshes),
        "triangles":faces,
        "boundary_edges":boundary,
        "nonmanifold_edges":nonmanifold,
        "texture_images":len(textures),
        "assumed_vertical_axis_from_sfM":["X","Y","Z"][axis],
        "color_printer_certified":False,
        "customer_likeness_verified":False,
        "operator_review_required":True,
        "warnings":[
            "SfM absolute scale is unknown without calibrated real-world reference.",
            "Automatic longest-axis alignment must be inspected for orientation.",
            "Non-manifold edges, wall thickness, disconnected parts, supports and textures require manual repair.",
            "Physical full-color print sample and supplier format acceptance are mandatory."
        ],
    }
    report.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    if not preview.is_file() or preview.stat().st_size<1024:
        raise RuntimeError("Blender did not export a valid preview GLB")
    if not (output/"replica.obj").exists():
        raise RuntimeError("Blender did not export OBJ")
    if not list(output.glob("*.mtl")) or not textures:
        raise RuntimeError("Blender did not export complete textured material package")


if __name__=="__main__":
    main()
