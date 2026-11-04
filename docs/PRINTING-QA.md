# Full-Color Printing — Operator QA Checklist

**Important:** No automated claim of “ready to print” is made by the current application.

## Inputs
- Client-approved version and order manifest
- GLB for digital appearance
- OBJ/MTL/PNG candidate for manufacturing
- Print vendor's exact full-color material, geometry, and color profile requirements

## Quality gates

| Gate | Acceptance method | Reject if |
|---|---|---|
| Identity & consent | Client approval, scope and rights check | No consent or unlicensed content |
| Customer likeness | Visual check against allowed reference | Wrong hair, outfit, recognizable features or accessories |
| Version integrity | Compare manifest, GLB and supplier print | Different version or unexplained edits |
| File completeness | OBJ, MTL and linked PNG all resolve | Texture missing or blank |
| Units/scale | Read dimensions in Blender, verify millimetres | Wrong size or orientation |
| Geometry | Mesh analysis / Blender 3D Print Toolbox | Open boundaries, internal duplicate geometry or non-manifold shells |
| Intersections | Boolean union or approved remesh | Unfused overlaps or fragile islands |
| Small features | Supplier minimum thickness profile | Hair strands, eyes, hands or accessories below minimum |
| Physical stability | Base footprint and balance check | Top-heavy unstable figurine |
| Full-color material | Printer-supported textures and material | Printer cannot reproduce colors |
| Preview-to-print proof | First-article printed sample / photographic comparison | Misleading visual difference |
| Packaging | Drop-test sample / protective inserts | Breakage under handling |

## Manufacturing repair in Blender
1. Import OBJ with original texture assets present and inspect normals and UV maps.
2. Set units to millimeters, check final height matches manifest.
3. Join/intersecting shells as appropriate, remove internal faces, Boolean union or use voxel remeshing when justified.
4. Verify eye/glasses/hair feature thickness using the supplier's material-specific recommendations.
5. Rebuild/verify UV textures after any destructive remesh, preview the export in the same color pipeline as supplier.
6. Run Blender's 3D Print Toolbox, repair errors and recheck dimensions.
7. Export exactly in the print service's accepted format, color space and up-axis.
8. Request a physical sample of each print material / process and confirm color gamut before customer orders.

## Material/color caveats
- OBJ + MTL + PNG are common but **not universally accepted**. Some suppliers require 3MF, WRL, or other formats.
- Untextured STL does not preserve color; do not substitute it for this product.
- Current exporter uses flat per-part color textures, **not extracted fabric graphics or photographic skin textures**.
- Print color varies by lighting, coating, printer calibration, resin/powder and supplier post-processing.
- Do not quote turnaround until the supplier accepts model, materials, finishing and order size.

## Pilot first article checklist
[ ] 50 mm solo
[ ] 80 mm solo (recommended standard)
[ ] 100 mm solo
[ ] One medium/long hair model
[ ] One waves/heart pose
[ ] Full-color texture package survives external vendor import
[ ] No breakage in packaging / transit
[ ] Color proof approved by customer

**Pilot sample acceptance is required before advertising fixed physical delivery dates.**


## Optional automated diagnostic report with Blender

This script generates a read-only JSON report of boundaries, per-component manifold flags and overall dimensions:

~~~bash
blender --background --factory-startup \
  --python tools/blender/inspect_print_candidate.py -- \
  model.obj review-report.json
~~~

Inspect the JSON report and manually perform supplier-specific union/remesh, thickness, texture and color proofing. **Passing the report does not certify a model for physical manufacturing.**
