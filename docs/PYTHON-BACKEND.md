# MINIMO Studio — Python Service Operations

## Actual architecture

**Vercel:** static customer-facing website and WebGL viewer.  
**Python FastAPI API:** private photo intake, server-authoritative projects, token-protected version approval, manufacturing candidate retrieval and operator review endpoints.  
**Python CPU worker:** durable SQLite job queue, photo-color extraction, trimesh chibi geometry and full-color OBJ/MTL/PNG/GLB candidate packaging.

No GPU is required for this generator. The output is *procedural chibi geometry* guided by sampled colors, **not high-fidelity photo-to-3D generative reconstruction**. Detailed clothing textures, photorealistic likeness, mesh union and certified printing remain separate R&D/manufacturing tasks.

### Data flow

~~~mermaid
flowchart LR
    UI[Customer on Vercel] -->|HTTPS / API| API[FastAPI]
    API --> DB[(SQLite single-host)]
    API --> PRIVATE[Private photo storage]
    DB --> WORK[CPU Python Worker]
    PRIVATE --> WORK
    WORK --> ASSET[GLB / OBJ / MTL / PNG ZIP]
    WORK --> DB
    API --> UI
    API --> OPS[Operator review endpoint]
    OPS --> PRINTER[Physical print after QA]
~~~

## Local developer setup

1. Install Python 3.12 and Node 22 (for frontend smoke checks).
2. Install API requirements:

~~~bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r services/python/requirements-dev.txt
cp .env.example .env
~~~

3. Use a password manager or generator to set a **different random 32+ character value** for `MINIMO_TOKEN_PEPPER` and `MINIMO_ADMIN_KEY` in `.env`.
4. For local testing only, set `MINIMO_PUBLIC_GENERATION=true` and ensure `MINIMO_ALLOWED_ORIGINS` includes `http://localhost:8000`.
5. Start the API and worker in separate terminals (load the environment variables from `.env`; Uvicorn supports `--env-file`):

~~~bash
PYTHONPATH=services/python uvicorn minimo.app:app --host 127.0.0.1 --port 8001 --env-file .env
# Terminal 2, with the same variables exported into its environment:
PYTHONPATH=services/python python -m minimo.worker
# Terminal 3:
python -m http.server 8000
~~~

For a cross-platform way to load environment variables and launch both services, use Docker Compose below.

6. Configure `api-config.js` in a **local test checkout** to set `window.MINIMO_API_URL = "http://127.0.0.1:8001"`, reload the frontend, and use the **Generate with Python** button.
7. The resulting order artifacts stay on the Python service disk—not in Vercel.

### Docker Compose

~~~bash
cp .env.example .env
# Edit .env, assign safe secrets, set MINIMO_PUBLIC_GENERATION=true ONLY for a protected pilot.
docker compose up --build -d
docker compose logs -f worker
~~~

The API listens on host loopback (`127.0.0.1:8001`). The private data volume is shared with a *single worker*. In production, deploy behind a properly configured HTTPS reverse proxy and enable backup, monitoring, edge rate limits and durable logging.

**Do not deploy this SQLite volume or background worker on Vercel serverless functions.** For multi-host scaling, migrate to PostgreSQL and a proper task broker.

### Production environment

- `MINIMO_ENV=production` causes startup to **fail closed** unless both secrets contain at least 32 characters.
- `MINIMO_PUBLIC_GENERATION=false` is the default until you explicitly enable public uploads.
- Set `MINIMO_ALLOWED_ORIGINS` to the exact HTTPS customer website domain.
- Set the frontend's `MINIMO_API_URL` to the real HTTPS Python API hostname, then redeploy the static site.
- Do not expose API keys in frontend JavaScript. Operator keys must be provided only through the admin interface in memory.
- Enable HTTPS/WAF, full disk encryption, image retention/deletion, signed offsite backups, dependency audits and a queue maintenance plan before paid customer traffic.

## API endpoints (current)

| Method | Route | Access |
|---|---|---|
| GET | `/api/v1/health` | Public, safe capability flags |
| POST | `/api/v1/projects` | Public if enabled; throttled multipart photo |
| POST | `/api/v1/projects/{id}/generate` | `X-Project-Token` |
| GET | `/api/v1/projects/{id}/jobs/{job_id}` | `X-Project-Token` |
| GET | `/api/v1/projects/{id}/versions/{vid}/preview` | `X-Project-Token` |
| POST | `/api/v1/projects/{id}/versions/{vid}/approve` | `X-Project-Token` |
| GET | `/api/v1/projects/{id}/versions/{vid}/package` | `X-Project-Token`; must approve |
| GET | `/api/v1/admin/queue` | `X-Admin-Key` |
| PATCH | `/api/v1/admin/versions/{vid}/production` | `X-Admin-Key` |

Generate request example:

~~~json
{
  "style": "classic",
  "hair": "short",
  "pose": "wave",
  "size_mm": 80,
  "seed": 100,
  "colors": {
    "skin": "#dca77c",
    "hair": "#31221f",
    "top": "#ed6c69",
    "bottom": "#637da8"
  }
}
~~~

The server hashes customer project tokens, privately stores metadata-stripped photos, validates inputs, caps the number of jobs and never treats browser requests as payment or physical printer approval.

## Quality gate

Passing API and Python generator tests means the pipeline **produces correct file structure**. It does **not** prove:
- A customer face is accurately reconstructed from a single photograph.
- Intersecting shells have been fused into one manufacturable watertight object.
- A printer will reproduce preview colors or accept the chosen material.
- Paid customer ordering, shipping, business registration and refund systems work.

**Operator MUST inspect physical material and the supplier's format/geometry constraints first.**

See [Printing QA](PRINTING-QA.md) and [Go-live plan](GO-LIVE.md).
