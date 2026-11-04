# Multi-Photo Human Capture Protocol

## Capture goals

MINIMO REAL uses multi-view photogrammetry. For high-fidelity humans, stability,
light, and genuine overlap matter more than raw photo count. A human who moves
between photos may yield a poor model even with 40 images.

### Recommended collection

| Required angle | Suggested images |
|:--|:--|
| Face and upper body: front/quarter/side | 8–12 |
| Head and hair, including rear | 6–10 |
| Torso and clothing from multiple directions | 8–12 |
| Lower body, shoes and back | 6–10 |
| Total capture set | 12–40 distinct, overlapping images |

A **full body** scan should ideally use a synchronized multi-camera arrangement
or very careful stationary capture. A **face-only** scan can be easier with
close-range views, but hair and reflective eyes remain difficult.

## Customer instructions

1. Obtain permission from everyone pictured.
2. Set up broad, soft, stable light and a visually textured but unobtrusive
   environment.
3. Keep the person as still as possible, with constant facial expression and
   consistent clothing.
4. Move the camera around the person in modest increments, maintaining roughly
   60–80% overlap between adjacent pictures.
5. Include front, 45°, true side and rear angles at approximately consistent
   camera distances.
6. Keep all of the face, hairline, ears, shoulders and clothing visible.
7. Avoid flash variation, motion blur, extreme perspective, mirrors and glass.
8. Do not upload multiple photos taken days apart in different poses or outfits.
9. If using different cameras, ensure consistent lenses/exposure or calibrate
   appropriately; a single camera is preferable for a basic session.
10. For physical dimension accuracy, include a real scale reference. Without
    one, COLMAP can recover relative structure but not absolute physical scale.

## When to reject a capture

- Multiple people or mixed subjects in one scan
- Missing side/rear views when a full-body model is requested
- Different clothing or hairstyles across views
- Motion blur, high glare or very small face pixels
- Large changes in pose or expression
- Nearly identical photos that provide no new camera baseline
- Occlusions covering important features

## Quality expectations

- The COLMAP stage may fail to register cameras if photos do not overlap.
- Photogrammetry estimates *visible surfaces*, not anatomy hidden behind clothing.
- Hair strands, transparent objects and shiny material are especially difficult.
- A professional realistic portrait may still require a manual sculpt, texture
  repair, or a multi-camera capture rig.
- No algorithm can guarantee an exact physical replica from an arbitrary set
  of phone images.

## Privacy

Photos of identifiable individuals are personal data. Consent, private storage,
transport encryption, access restrictions, retention and deletion are required.
The repository does not contain real customer capture photographs.
