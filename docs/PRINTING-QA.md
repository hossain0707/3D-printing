# MINIMO REAL — Manufacturing Acceptance Protocol

A realistic 3D preview **does not imply** that a manufacturing vendor can print
the model. The pipeline exports a **candidate** with a JSON quality report.

## Operator inspection gates

| Check | Evidence | Reject or repair if |
|:--|:--|:--|
| Identity and permission | Customer consent and approved preview | Subject did not consent / wrong identity |
| Reconstruction likeness | Compare front, sides and back with submitted photos | Wrong face, hairline, profile, outfit |
| Model integrity | Blender non-manifold and boundaries report | Holes, disconnected shells or internal artifacts |
| Metric dimensions | Measured physical reference and size target | Wrong scale, upside-down orientation, missing calibration |
| Surface thickness | Material-specific printer thickness checks | Weak ears, hair, clothing or shoes |
| Real-world stability | Base placement and center-of-mass reasoning | Model falls or lacks a stable support |
| Texture atlas | Supplier imports OBJ+MTL+all referenced images | Missing photos, textures or UV coordinates |
| Color proof | ICC profile and physical vendor swatches | Unsupported material, inaccurate skin/clothing colors |
| Print acceptance | Vendor-specific geometry and material constraints | Vendor declines the model |
| Physical sample | Print, clean, coat and package one sample | Visible distortions, weakness or unacceptable finish |

## Geometry report

Headless Blender's \`prepare_realistic.py\` produces an actual JSON report
recording source type, approximate target mm dimensions, number of mesh parts,
polygon count, non-manifold and boundary edges and texture count.

It always sets \`status: REVIEW_REQUIRED\`. This is deliberately conservative:
an automatic non-manifold count cannot establish complete printability, inner
shell quality, minimum feature thickness or likely physical appearance.

## Corrective modeling

Use Blender or the selected vendor's repair tools to:
- fix orientation, especially when auto-alignment chose the wrong longest axis;
- determine true physical size using a measured reference;
- remove surface noise, close holes and perform union/voxel remesh if needed;
- preserve the face, clothing and photographic textures when repairing geometry;
- inspect all UV maps and material images after any destructive modifier;
- add supports or a stable display base if required by the chosen technology;
- confirm exact export format. Some full-color vendors require 3MF, VRML or
  specific OBJ+MTL+PNG packaging; plain STL loses color.

## Sample acceptance

Do not advertise guaranteed exact resemblance or color until at least several
consented volunteers have received representative full-color physical samples.
Record pass/fail by face, hair, clothing, scale, mesh failures, vendor acceptance,
breakage and customer approval.

**The current project has not yet passed a verified physical first-article test.**
