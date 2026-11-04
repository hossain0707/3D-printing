# MINIMO REAL — Engineering Architecture

## System boundary

The customer-facing Vercel website is a static application. It does not store
photographs and **cannot reconstruct a model locally**. It submits authenticated
photo collections to a separately hosted Python API only after the customer
agrees to the consent statement and the API reports that processing is enabled.

~~~mermaid
sequenceDiagram
    participant B as Customer Browser
    participant A as FastAPI
    participant D as SQLite / private disk
    participant W as Python GPU Worker
    participant C as COLMAP
    participant L as Blender
    participant O as Operator
    B->>A: POST multipart 12-40 photos + consent
    A->>A: MIME / decode / size / duplicate validation
    A->>D: Store EXIF-stripped photos + HMAC owner token digest
    A-->>B: Project ID + temporary owner token
    B->>A: POST reconstruction request
    A->>D: Commit queued job
    W->>D: Atomic queue claim
    W->>C: Feature extraction / matching / SfM
    W->>C: Dense CUDA stereo / fused surface / photo textures
    W->>L: Import textured model, scale, export GLB / OBJ
    W->>D: Commit preview + manufacturing candidate + QA JSON
    B->>A: Poll authenticated job
    A-->>B: Real stage and status
    B->>A: GET authenticated GLB preview
    B->>A: POST approve real version
    B->>A: GET private print candidate ZIP
    O->>A: Inspect QA report and update operator decision
~~~

## Runtime modules

| Module | Execution environment | Role |
|:--|:--|:--|
| \`index.html\`, \`styles.css\`, \`app.js\` | Vercel static HTTPS | Photo capture, explicit consent, real-model 3D preview |
| \`admin.html\`, \`admin.js\` | Vercel static HTTPS | Thin private operator UI; actual authorization enforced server-side |
| \`minimo.app\` | Persistent Python server | Input validation, project authorization, queue insertion, artifacts |
| \`minimo.db\` | SQLite WAL on private persistent disk | Local project/job/version state |
| \`minimo.worker\` | Dedicated processing host | Durable job processing and retention cleanup |
| \`minimo.photogrammetry\` | Worker | COLMAP command orchestration and strict artifact verification |
| \`tools/blender/prepare_realistic.py\` | Headless Blender 4.4+ | Photo-derived texture import, scale conversion, QA JSON, GLB/OBJ export |

### Reconstruction stages (must all succeed)

1. \`colmap feature_extractor\` — CPU feature extraction
2. \`colmap exhaustive_matcher\` — CPU image matching
3. \`colmap mapper\` — real camera pose and sparse 3D estimation
4. \`colmap image_undistorter\` — calibrated images
5. \`colmap patch_match_stereo\` — CUDA dense multi-view reconstruction
6. \`colmap stereo_fusion\` — fused depth
7. \`colmap poisson_mesher\` — actual estimated surface geometry
8. \`colmap mesh_texturer\` — photograph-derived UV texture atlas
9. Headless Blender — imported real textured geometry; metric candidate export and GLB
10. Private ZIP packaging and QA report

No automatic or fallback creation of generic heads, bodies or fake scanned figures exists
in this active flow.

## Security boundaries

- Owner access: a random project token returned **only once** to the browser;
  its database representation is HMAC-SHA256 using a private server pepper.
  All project reads, preview, approval, download and deletion check that token.
- Operator access: a separate server-side admin key, compared in constant time;
  no credentials are shipped in the public website source. For commercial use,
  replace the shared operator key with an audited OIDC identity system and roles.
- Client photo privacy: upload consent, type/size limits, independent JPEG
  re-encode, EXIF stripping, private data paths and deletion.
- Browser storage: temporary project token uses \`sessionStorage\`, not public URL.
  Client-side XSS prevention, CSP and dependency review remain mandatory.
- Processing: actual command binaries are launched using argument arrays,
  \`shell=False\`, per-stage timeouts and server-owned working directories.
  A hardened dedicated container/user with memory and CPU quotas is required
  before accepting untrusted high-volume public uploads.
- Cost protection: job concurrency caps, project job count caps and per-IP
  memory throttling. These are **single-process controls**; public traffic
  requires edge WAF and distributed rate limiting.
- Data retention: configurable TTL. The worker purges expired finished
  projects. Run maintenance independently when the GPU worker is offline.
- HTTPS: required externally. The provided API-only Docker Compose binds
  only to loopback, not the public internet.

## Scaling migration

The current implementation is an initial **single-host operational foundation**,
not a distributed high-availability system.

For multi-worker or commercial scale:
- Move SQLite tables to PostgreSQL with proper migrations, backups and row ownership.
- Put photos and outputs in private object storage with short-lived scoped access.
- Use a durable broker (e.g. Redis Streams, RabbitMQ or managed queues) to allocate GPU workers.
- Add real customer accounts and operator OIDC roles with audit trails.
- Add edge rate limits, signed upload URLs, antivirus/image validation, retention and backup verification.
- Add payment gateway **only after merchant approval**, signed webhooks, server-side pricing and refund handling.
- Evaluate likeness benchmarks and printing tolerances with real consenting volunteers.

## Accuracy limitations

Multi-view photogrammetry depends on texture, image overlap, stable lighting and
a still subject. Moving people, shiny fabrics and thin hair do not reconstruct
reliably in every case. The physical scale of SfM is arbitrary without a real-world
reference; the automatic longest-axis sizing is an estimate requiring operator
measurement. A model having GLB/OBJ files is not proof of physical printability.
