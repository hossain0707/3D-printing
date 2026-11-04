"""Deterministic, CPU-friendly chibi geometry and honest print-candidate export.

The generated components are individually closed but overlap. This is not a
watertight union and must be inspected/repaired before manufacturing.
"""
from __future__ import annotations

import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageStat

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_hex(value: str) -> str:
    if not HEX.fullmatch(value):
        raise ValueError("Expected an RGB hex color")
    return value.lower()


def _rgba(value: str) -> tuple[int, int, int, int]:
    value = validate_hex(value).lstrip("#")
    return (*tuple(bytes.fromhex(value)), 255)


def _sample(photo: Image.Image, bounds: tuple[float, float, float, float], fallback: str) -> str:
    w, h = photo.size
    x0, y0, x1, y1 = bounds
    region = photo.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1)))
    if not region.width or not region.height:
        return fallback
    values = [int(n) for n in ImageStat.Stat(region.convert("RGB")).median[:3]]
    if max(values) > 247 or max(values) < 15:
        return fallback
    return "#" + "".join(f"{v:02x}" for v in values)


def colors_from_photo(photo_path: Path, overrides: dict[str, str] | None = None) -> dict[str, str]:
    with Image.open(photo_path) as image:
        image = image.convert("RGB")
        # Deliberately approximate; different portrait/body crops need manual correction.
        palette = {
            "skin": _sample(image, (.46, .18, .54, .29), "#dca77c"),
            "hair": _sample(image, (.42, .04, .58, .10), "#31221f"),
            "top": _sample(image, (.40, .56, .60, .64), "#ed6c69"),
            "bottom": _sample(image, (.42, .77, .58, .84), "#637da8"),
        }
    for key, value in (overrides or {}).items():
        if key not in palette:
            raise ValueError(f"Unsupported color control: {key}")
        palette[key] = validate_hex(value)
    return palette


def _ellipsoid(name: str, rgb: str, origin: tuple[float, float, float],
               scales: tuple[float, float, float]) -> tuple[str, trimesh.Trimesh, str]:
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1)
    mesh.apply_scale(scales)
    mesh.apply_translation(origin)
    mesh.visual.vertex_colors = np.tile(np.array(_rgba(rgb), dtype=np.uint8), (len(mesh.vertices), 1))
    return name, mesh, rgb


def _cylinder(name: str, rgb: str, origin: tuple[float, float, float],
              radius: float, height: float) -> tuple[str, trimesh.Trimesh, str]:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=48)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2, [1, 0, 0]))
    mesh.apply_translation(origin)
    mesh.visual.vertex_colors = np.tile(np.array(_rgba(rgb), dtype=np.uint8), (len(mesh.vertices), 1))
    return name, mesh, rgb


def build_character(style: str, hair: str, pose: str,
                    palette: dict[str, str], seed: int = 11) -> list[tuple[str, trimesh.Trimesh, str]]:
    if style not in {"classic", "dreamy", "collector"}:
        raise ValueError("Unknown style")
    if hair not in {"short", "medium", "long", "bun"}:
        raise ValueError("Unknown hairstyle")
    if pose not in {"stand", "wave", "hug"}:
        raise ValueError("Unknown pose")
    skin, dark, top, pants = (palette[k] for k in ("skin", "hair", "top", "bottom"))
    model: list[tuple[str, trimesh.Trimesh, str]] = []
    add = model.append
    base = {"classic": "#f4e7d7", "dreamy": "#dec9ed", "collector": "#f7d7a5"}[style]
    add(_cylinder("display_base", base, (0, .2, 0), 1.91, .40))
    for side in (-1, 1):
        add(_ellipsoid(f"trouser_{side}", pants, (side*.47, .92, 0), (.40, .73, .45)))
        add(_ellipsoid(f"shoe_{side}", "#f4e9db", (side*.47, .49, .25), (.46, .29, .58)))
    add(_ellipsoid("torso", top, (0, 2.35, 0), (.92, 1.15, .7)))
    add(_ellipsoid("collar", "#fff3e7", (0, 3.27, .48), (.42, .18, .24)))
    hands = {
        "wave": ((-1.1, 1.82, .1), (1.64, 3.48, .08)),
        "stand": ((-1.1, 1.82, .1), (1.1, 1.82, .1)),
        "hug": ((-.45, 2.42, .86), (.45, 2.42, .86)),
    }[pose]
    sleeves = {
        "wave": ((-1.03, 2.35, .02), (1.13, 3.07, 0)),
        "stand": ((-1.03, 2.35, .02), (1.03, 2.35, .02)),
        "hug": ((-.84, 2.54, .58), (.84, 2.54, .58)),
    }[pose]
    for i, side in enumerate((-1, 1)):
        add(_ellipsoid(f"sleeve_{i}", top, sleeves[i], (.38, .67, .42)))
        add(_ellipsoid(f"hand_{i}", skin, hands[i], (.31, .31, .31)))
    if pose == "hug":
        add(_ellipsoid("heart", "#df627e", (0, 2.48, 1.06), (.34, .33, .22)))
    add(_ellipsoid("face", skin, (0, 4.65, .04), (1.43, 1.43, 1.20)))
    for side in (-1, 1):
        add(_ellipsoid(f"ear_{side}", skin, (side*1.39, 4.47, .06), (.25, .32, .24)))
        add(_ellipsoid(f"eye_{side}", "#252124", (side*.52, 4.79, 1.17), (.21, .26, .10)))
        add(_ellipsoid(f"eye_light_{side}", "#fffaf6", (side*.52-.05, 4.87, 1.25), (.06, .075, .03)))
        add(_ellipsoid(f"blush_{side}", "#eba1a0", (side*.83, 4.38, 1.04), (.25, .11, .065)))
    add(_ellipsoid("nose", "#be8d74", (0, 4.46, 1.24), (.08, .09, .07)))
    add(_ellipsoid("smile", "#774457", (0, 4.19, 1.20), (.18, .08, .06)))
    h = {"short":1.15, "medium":1.50, "long":1.94, "bun":1.15}[hair]
    add(_ellipsoid("hair_back", dark, (0, 4.92, -.49), (1.47, h, .89)))
    add(_ellipsoid("hair_top", dark, (0, 5.67, -.02), (1.43, .81, 1.13)))
    if hair in {"medium", "long"}:
        for side in (-1, 1):
            add(_ellipsoid(f"hair_lock_{side}", dark, (side*1.21, 4.52, -.01), (.36, 1.59 if hair=="long" else 1.03, .54)))
    if hair == "bun":
        add(_ellipsoid("hair_bun", dark, (.74, 6.15, -.1), (.55, .53, .51)))
    rng = np.random.default_rng(seed)
    for n in range(5):
        add(_ellipsoid(f"fringe_{n}", dark, (-1.05+n*.52, 5.55-float(rng.uniform(0,.22)), .98),
                       (.30, float(rng.uniform(.31,.46)), .21)))
    if style == "collector":
        add(_ellipsoid("star_accent", "#ffe7a3", (1.1, 5.41, 1.08), (.17, .19, .10)))
    return model


def create_bundle(photo_path: Path, output_path: Path, project_id: str,
                  version_id: str, controls: dict) -> dict:
    size = int(controls.get("size_mm", 80))
    if size not in (50, 80, 100):
        raise ValueError("Unsupported physical size")
    palette = colors_from_photo(photo_path, controls.get("colors"))
    pieces = build_character(controls["style"], controls["hair"], controls["pose"],
                             palette, int(controls.get("seed", 11)))
    scene = trimesh.Scene()
    for name, mesh, _ in pieces:
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    xyz = scene.bounds
    actual_height = xyz[1, 1] - xyz[0, 1]
    factor = size / actual_height

    # Each geometry is individually closed but components overlap. No false union claim.
    scene_scaled = trimesh.Scene()
    for name, mesh, rgb in pieces:
        scaled = mesh.copy()
        scaled.vertices = (scaled.vertices - np.array([(xyz[0,0]+xyz[1,0])/2,
                                xyz[0,1], (xyz[0,2]+xyz[1,2])/2]))*factor
        scene_scaled.add_geometry(scaled, node_name=name, geom_name=name)
    glb = scene_scaled.export(file_type="glb")

    obj = ["# MINIMO Studio print candidate - units: millimeters, Y up",
           "mtllib miniature.mtl"]
    mtl = ["# Generated per-part flat color textures"]
    pngs: dict[str, bytes] = {}
    vertex_offset = 1
    for name, mesh, rgb in pieces:
        material = "rgb_" + validate_hex(rgb)[1:]
        if material+".png" not in pngs:
            pic = Image.new("RGB", (16, 16), tuple(bytes.fromhex(rgb[1:])))
            buff = io.BytesIO(); pic.save(buff, format="PNG")
            pngs[material+".png"] = buff.getvalue()
            mtl.extend(["newmtl "+material, "Ka 0 0 0", "Kd 1 1 1",
                        "d 1.0", "map_Kd "+material+".png", ""])
        obj.extend(["o "+name, "usemtl "+material])
        vertices = (mesh.vertices-np.array([(xyz[0,0]+xyz[1,0])/2,xyz[0,1],
                                           (xyz[0,2]+xyz[1,2])/2]))*factor
        for v in vertices:
            obj.append(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}")
        obj.append("vt 0.5 0.5")
        for face in mesh.faces:
            a,b,c = (int(i)+vertex_offset for i in face)
            obj.append(f"f {a}/1 {b}/1 {c}/1")
        vertex_offset += len(mesh.vertices)

    manifest = {
        "project_id": project_id, "version_id": version_id,
        "size_mm": size, "style": controls["style"], "hair": controls["hair"],
        "pose": controls["pose"], "palette": palette,
        "base_inscription": controls.get("inscription", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRINT_CANDIDATE_ONLY", "customer_payment": "NOT_COLLECTED",
        "mesh_union_verified": False, "physical_print_verified": False,
        "face_likeness": "stylized estimate, not photo-exact",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("preview/approved-character.glb", glb)
        archive.writestr("print-candidate/miniature.obj", "\n".join(obj)+"\n")
        archive.writestr("print-candidate/miniature.mtl", "\n".join(mtl)+"\n")
        for filename, data in pngs.items():
            archive.writestr("print-candidate/"+filename, data)
        archive.writestr("ORDER-MANIFEST.json", json.dumps(manifest, indent=2))
        archive.writestr("READ-BEFORE-PRINTING.txt",
            "PRINT CANDIDATE ONLY. Inspect intersecting shells, union/remesh, "
            "manifold integrity, minimum feature thickness, full-color textures "
            "and physical supplier proof before accepting a customer order.\n")
    return {"manifest": manifest, "parts": len(pieces),
            "glb_bytes": len(glb), "zip_bytes": output_path.stat().st_size}
