# Deploying the MINIMO REAL Python Processing Service

**Status:** Python API and reconstruction code exist in GitHub; the CPU/GPU
binary stack and a public HTTPS processing server have not been provisioned in
this repository. The Vercel frontend correctly disables upload while the API
is disconnected. There are no fake success responses.

## Prerequisites

- Python 3.12
- A persistent Linux host, preferably Ubuntu 24.04
- COLMAP CLI **with CUDA dense multi-view stereo support**
- A compatible NVIDIA GPU and driver for COLMAP PatchMatch (GPU memory needs
  depend on photo count and image size; start with 16–24 GB VRAM)
- Blender **4.4 or later** and its Python OBJ/glTF operators
- 16–32 GB system RAM as a practical initial target, plus several GB of disk
  capacity for each reconstruction
- HTTPS reverse proxy, host firewall and restricted storage/backup policy

The pipeline is real COLMAP geometry reconstruction; it does **not** call a
proprietary paid photo-to-avatar service.

**Official installation documentation:**
- COLMAP: https://colmap.github.io/install.html
- COLMAP CLI: https://colmap.github.io/cli.html
- Blender: https://www.blender.org/download/

## Local installation

~~~bash
git clone https://github.com/hossain0707/3D-printing.git
cd 3D-printing
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r services/python/requirements-dev.txt
cp .env.example .env
~~~

Generate **two distinct strong secrets** locally without copying them into chat:

~~~bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
~~~

Set \`MINIMO_TOKEN_PEPPER\` and \`MINIMO_ADMIN_KEY\` separately in \`.env\`.
Keep \`MINIMO_ENABLE_UPLOADS=false\` until the host and HTTPS protection are ready.

For the developer test machine only, use \`MINIMO_ENV=development\`. In
production, set \`MINIMO_ENV=production\` to make missing/short secrets a
hard startup failure.

### Native Python service and worker

In the root of the cloned repository (Linux/macOS shell):

~~~bash
set -a
source .env
set +a
export PYTHONPATH="$PWD/services/python"
uvicorn minimo.app:app --host 127.0.0.1 --port 8001
~~~

Start the worker in **another terminal**, with the *same environment and data directory*:

~~~bash
set -a
source .env
set +a
export PYTHONPATH="$PWD/services/python"
command -v colmap
command -v blender
python -m minimo.worker
~~~

If either binary is missing, the worker **exits rather than pretending**
reconstruction is working. A COLMAP build without CUDA dense stereo may start
but then fail at the real multi-view stage; verify with the actual pilot scan.

### Frontend local preview

~~~bash
python -m http.server 8000
~~~

Open http://localhost:8000. For local Python integration, set
\`window.MINIMO_API_URL\` to \`http://127.0.0.1:8001\` in \`api-config.js\`
and reload the page. In production configure only the real public HTTPS origin.

The customer frontend needs a live API: its 3D viewer will **not** fabricate
a stand-in face or model.

## Docker Compose: API only

~~~bash
docker compose up --build -d
~~~

This launches a non-root API on loopback with a private persistent volume.
It **does not** include GPU-enabled COLMAP or Blender and therefore does not
start the reconstruction worker. Run both API and worker natively with a shared
\`MINIMO_DATA_DIR\`, or build a custom GPU worker image with access to the
*same* persistent files and a supported CUDA COLMAP installation.

Do not point the worker to a different empty data directory or attempt to run
a CPU-only COLMAP dense pipeline. The API, SQLite file, images and outputs
must reside on a compatible shared private persistent volume.

**Vercel cannot replace the long-running GPU worker.** It hosts only the static
customer-facing site and the operator console.

## HTTPS deployment

1. Deploy the Python service on a persistent host with GPU worker access.
2. Terminate HTTPS at a trusted reverse proxy or load balancer.
3. Bind the FastAPI origin to localhost or a private network only.
4. Limit request body size to the configured maximum (~240 MB), add real IP
   identification only from trusted proxies, edge rate limiting and observability.
5. Set \`MINIMO_ALLOWED_ORIGINS\` to the **exact customer website HTTPS origin**.
6. Set \`MINIMO_ENABLE_UPLOADS=true\` **only after** consent/privacy policy,
   retention and secure data access are in place.
7. Update the public \`api-config.js\` with the processing HTTPS origin (never
   a secret), then redeploy the static Vercel site.
8. Confirm GET \`/api/v2/health\` reports installed COLMAP and Blender binaries.
9. Upload a real, consented 12–40 photo set; confirm a 3D preview, actual
   photo-derived textures and valid private download.

## API v2 routes

| Method | Endpoint | Access |
|:--|:--|:--|
| GET | \`/api/v2/health\` | Public capability data |
| POST | \`/api/v2/projects\` | Consent + 12–40 multipart image files |
| POST | \`/api/v2/projects/{id}/reconstruct\` | X-Project-Token |
| GET | \`/api/v2/projects/{id}\` | X-Project-Token |
| GET | \`/api/v2/projects/{id}/jobs/{job}\` | X-Project-Token |
| GET | \`/api/v2/projects/{id}/versions/{version}/preview\` | X-Project-Token |
| GET | \`/api/v2/projects/{id}/versions/{version}/report\` | X-Project-Token |
| POST | \`/api/v2/projects/{id}/versions/{version}/approve\` | X-Project-Token |
| GET | \`/api/v2/projects/{id}/versions/{version}/package\` | X-Project-Token + customer approval |
| DELETE | \`/api/v2/projects/{id}\` | X-Project-Token |
| GET | \`/api/v2/admin/queue\` | X-Admin-Key |
| GET | \`/api/v2/admin/versions/{version}/package\` | X-Admin-Key |
| PATCH | \`/api/v2/admin/versions/{version}\` | X-Admin-Key |

No endpoint marks a payment as successful. All print/ship states are manually
recorded operator attestations.

## Test and operational QA

~~~bash
npm test
python -m pytest services/python/tests -q
python -m compileall -q services/python tools/blender
~~~

These automated tests exercise authentication, input rejection, queued jobs and
access protection with **test doubles of external GPU reconstruction**. They
do not prove actual COLMAP CUDA operation or physical resemblance.

When the GPU worker is offline, retention cleanup must still be scheduled:
\`python -m minimo.maintenance\` via a daily OS scheduler with the same secure
\`MINIMO_DATA_DIR\`. Backups must honor the same retention policy.

## Critical production prerequisites

- Stable, secure processing host and tested GPU model
- Verified TLS/WAF/restricted access/backup restores/logging
- Customer consent language and local law review for face photos
- Proper customer accounts and real multi-factor operator identities (current
  token model is a pilot foundation)
- Handling for GPU failure, retry, refunds, cancellation and customer support
- Proven printability/texture validation and an actual physical first article
- A separate verified merchant payment integration, if accepting orders

**Never interpret green CI checks as “photo-identical person” or “print ready”.**
