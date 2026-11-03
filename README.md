# ✳ MINIMO Studio — Photo-to-Chibi 3D Miniature Atelier

> **A little you. A lot of joy.** A beautifully animated, mobile-responsive customer experience for creating a personalized, full-color cartoon miniature from a single customer photograph, with a rotatable 3D preview, regeneration, approval and manufacturing handoff.

**Repository:** https://github.com/hossain0707/3D-printing  
**Owner & copyright:** © 2026 Md Najmul Hossain. All rights reserved.  
**Status:** Deployed customer-facing **design studio and print-candidate exporter**. **Not a complete commerce/production service yet.** See launch requirements below.

## Product capabilities (implemented)

| Capability | Status | Details |
|---|---|---|
| Responsive branded homepage | ✅ | Hero 3D animation, gallery cards, accessible sections and FAQ |
| Client photo upload | ✅ | Local JPG, PNG or WEBP; max 8 MB |
| Face landmark AI | ✅ Optional | MediaPipe CPU/WASM, loaded in customer's browser when available; fails gracefully |
| Photo-color matching | ✅ Approximate | Samples skin, hair and outfit regions; editable color controls |
| 3D miniature generation | ✅ | Parametric chibi shapes, hair styles, colors and poses |
| True 3D viewer | ✅ | WebGL via Three.js; rotate/zoom on mobile and desktop |
| Regenerate | ✅ | New procedural look with consistent selected colors and configurable features |
| Approve version | ✅ | Freeze version and export specification in current session |
| Manufacturing export | ✅ Candidate | GLB preview; OBJ + MTL + PNG UV textures, measured in millimeters |
| Price estimate | ✅ Indicative | Demonstration retail target only, not a supplier quote |
| Uploaded photo sent to server | ❌ | **No**; the current app processes photos locally |
| Persistent online orders | ❌ | Requires secure backend, authentication and storage |
| Payment / invoicing | ❌ | Requires verified commercial payment gateway account |
| Automatic printer acceptance | ❌ | Geometry/material checks and supplier approval required |
| Fully faithful reconstruction from one photo | ❌ | Hidden geometry and precise likeness cannot be inferred reliably |

> **Engineering distinction:** MediaPipe landmarks help tune parametric models; the project does **not** use a trained general photo-to-3D generative diffusion model. “AI-assisted” describes the optional face-analysis step. The base model is deterministic procedural geometry.

## Architecture

\`\`\`mermaid
flowchart LR
    A[Customer photo] --> B[Browser image analysis]
    B --> C[Optional on-device MediaPipe face landmarks]
    B --> D[Color samples]
    C --> E[Chibi template generator]
    D --> E
    E --> F[Three.js 360-degree preview]
    F --> G{Approve?}
    G -->|Regenerate / edit| E
    G -->|Yes| H[Freeze design version]
    H --> I[GLB preview + OBJ/MTL/PNG ZIP]
    I --> J[Operator QA / mesh repair]
    J --> K[Full-color printer proof & quote]
    K --> L[Physical print / packaging]
\`\`\`

**Frontend:** Semantic HTML5, plain CSS, JavaScript modules, Three.js r170, optional MediaPipe Tasks Vision.  
**Export:** GLTFExporter, custom metric OBJ/MTL exporter, solid-color PNG textures, JSZip.  
**Deploy:** Vercel static website, no backend secrets and no paid compute required.  
**Customer PII:** Uploaded photos remain in local browser memory for the current session. They are not added to the exported ZIP.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PRINTING-QA.md](docs/PRINTING-QA.md) and [docs/GO-LIVE.md](docs/GO-LIVE.md).

## Quick start

### Open locally

Static ES modules require HTTP serving (do not open index.html using file://).

\`\`\`bash
git clone https://github.com/hossain0707/3D-printing.git
cd 3D-printing
python -m http.server 8000
# open http://localhost:8000
\`\`\`

or use any static HTTP server. Internet connectivity is needed to download the Three.js, JSZip and optional MediaPipe dependencies, as currently delivered via pinned public CDNs.

### Deploy to Vercel

1. Import this GitHub repository into a Vercel project.
2. Framework preset: **Other**, root directory: repository root, no build command.
3. Output directory: repository root (default for static projects).
4. Deploy the main branch. HTTPS is required for the best client-side model functionality.

\`\`\`bash
npm test
\`\`\`

Runs source-structure smoke tests. **This is not a substitute for browser E2E, print validation or security testing.**

## End-to-end customer design flow

1. Upload one clear photo with visible face and outfit. Avoid other people, blurry shots, complex backgrounds and inappropriate copyrighted marks.
2. Browser extracts rough color patches. Optional CPU landmark detection estimates facial proportions.
3. Select chibi personality, hairstyle, pose, size (50, 80, 100 mm) and inscription.
4. Review 360-degree 3D model and regenerate or edit until satisfied.
5. Approve the current version, then download its ZIP.
6. Operator inspects mesh watertightness, interpenetrations, minimum thickness, proportions, pose, texture and print profile.
7. Print supplier checks material, color format and price; after commercial backend/payment launch, paid order can proceed.

### ZIP output

\`\`\`text
minimo-approved-v4-80mm.zip
├── ORDER-MANIFEST.json
├── READ-BEFORE-PRINTING.txt
├── preview/
│   └── approved-character.glb
└── print-candidate/
    ├── miniature.obj
    ├── miniature.mtl
    ├── color_dca77c.png
    └── ... additional material textures
\`\`\`

- OBJ vertices are exported in **millimeters** with Y-up, normalized to the selected final height.
- Each procedural surface gets UV coordinates and a color PNG through the MTL specification.
- Several geometries are separate intersecting shells, not a validated manifold union. This is **not automatically print-safe**. Export remains a candidate until cleaned and tested.
- Full-color printing is a separate manufacturing service; standard monochrome FDM/SLA printing does not reproduce the intended texture colors.
- Sample retail prices in the demo are illustrative and **not a payment offer**.

## Privacy and safety

- Photos are read with a File input / canvas; the app does not transmit photo pixel data to a backend.
- Third-party JavaScript and AI model assets are downloaded from public CDNs. For a commercial release, self-host pinned audited assets, add a strict CSP and complete vendor/privacy assessment.
- No customer payment, shipping address or real order information is collected on the current site.
- Obtain consent before collecting personal photos in a future backend, provide retention/deletion policies and protect customer models in private storage.
- Confirm rights to reproduce uniforms, brands, fictional characters and likenesses before production.
- Protect operator roles with server-side authentication. Never implement admin authority through a browser-only flag.

## Testing

\`\`\`bash
node --test tests/smoke.test.js
\`\`\`

Manual acceptance:
- Upload front-facing portrait and full-body photos in Chrome/Edge/Safari mobile.
- Confirm CPU AI model fallback succeeds if the model host cannot load.
- Regenerate and edit a color; verify prior approval becomes invalid.
- Approve, export, and unzip: verify GLB, OBJ/MTL/PNG, millimeter height and manifest.
- Open OBJ with textures in Blender; run 3D Print Toolbox and supplier-specific QA.
- Inspect the production HTML over HTTPS and console for missing CDN dependencies.

## Product roadmap

- **V1 interactive studio:** implemented, functional demo with parametric 3D.
- **V2 production export:** implemented as *print candidates*. Supplier-verified union/remesh and pilot physical color proofs remain to be done.
- **V3 commerce:** UI, processes and architecture documented; **persistent backend, real accounts, checkout, admin production queue, notifications and shipping integration are not configured**. Do not market the current public demo as a fully operating store.
- **V4 improvement:** approved asset catalog, hair segmentation, robust garment parsing, richer texture synthesis, local GPU or cloud reconstruction, automatic printer repair, queue management and post-print QC analytics.

## Intellectual property

Original project materials are **proprietary**. See [LICENSE](LICENSE). Open-source libraries remain governed by their own licenses. No rights to customer photos, third-party logos or licensed characters are transferred by this repository.

**Owner:** Md Najmul Hossain · GitHub [hossain0707](https://github.com/hossain0707)
