"""Read-only Blender manufacturing diagnostics, not automatic certification.

Usage:
    blender -b --factory-startup -P tools/blender/inspect_print_candidate.py -- \
      model.obj report.json

The user must inspect and repair the model manually. Do not claim printer approval.
"""
import json
import sys
from pathlib import Path

import bpy
import bmesh


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if len(args) != 2:
        raise SystemExit("Usage: Blender -b -P inspect_print_candidate.py -- input.obj report.json")
    source, report_path = [Path(arg).resolve() for arg in args]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(source), forward_axis="Y", up_axis="Z")
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objects:
        raise RuntimeError("Input contains no mesh objects")
    points=[]
    report={
        "input_file": source.name,
        "status": "REVIEW_REQUIRED_NOT_CERTIFIED",
        "individual_meshes": len(objects),
        "warnings": [],
        "objects": []
    }
    for obj in objects:
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        edge_count=len(bm.edges)
        boundary=sum(1 for e in bm.edges if e.is_boundary)
        nonmanifold=sum(1 for e in bm.edges if not e.is_manifold)
        report["objects"].append({
            "name":obj.name, "faces":len(bm.faces),
            "edges":edge_count, "boundary_edges":boundary,
            "nonmanifold_edges":nonmanifold,
            "watertight_component":nonmanifold == 0
        })
        bm.free()
        for corner in obj.bound_box:
            vec=obj.matrix_world @ __import__("mathutils").Vector(corner)
            points.append(tuple(vec))
    mins=[min(p[n] for p in points) for n in range(3)]
    maxs=[max(p[n] for p in points) for n in range(3)]
    report["bounds_native_units"]={"min":mins,"max":maxs,"size":[maxs[i]-mins[i] for i in range(3)]}
    if len(objects)>1:
        report["warnings"].append("Multiple components; geometric union/internal-intersection analysis required.")
    if any(o["nonmanifold_edges"]>0 for o in report["objects"]):
        report["warnings"].append("At least one component contains non-manifold edges.")
    report["warnings"].append(
        "Wall thickness, internal intersections, print axis, material, textures and physical color proof not certified."
    )
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("MINIMO report written to",report_path)


if __name__ == "__main__":
    main()
