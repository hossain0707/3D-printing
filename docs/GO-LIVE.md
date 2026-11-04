# MINIMO REAL — Launch Gate

## Existing implementation

- New realistic multi-photo frontend and real-model-only viewer
- Private upload with consent, size/type checks and duplicate detection
- Owner-scoped photo project access and explicit delete endpoint
- Transactional generation job persistence and worker status
- COLMAP real SfM/MVS/Poisson/photographic texturing command orchestration
- Blender output conversion, metric candidate, GLB and QA report
- Private customer package approval/download
- Restricted operator queue and manual quality statuses
- GitHub automated frontend and Python API tests

## Still not verified / not deployed

| Requirement | Current state |
|:--|:--|
| CUDA-ready COLMAP GPU host | Not provisioned |
| Python processing API publicly reachable via HTTPS | Not connected |
| Real human dataset end-to-end successful reconstruction | Not verified |
| Full-color print supplier contract and test print | Not completed |
| Measured face/garment likeness and customer satisfaction | Not measured |
| Printer-ready geometry, strength and color | Not certified |
| Customer sign-in, real durable commerce orders | Not implemented |
| Payment/refunds/shipping | Not implemented |
| Formal privacy notice, secure backup retention, WAF/monitoring | Requires commercial deployment |
| Business/merchant registration and applicable employment permission | Requires owner's local review |

## Non-negotiable acceptance before paid orders

1. Deploy and secure the processing API/worker on tested infrastructure.
2. Capture consented multi-view images and prove at least one **real** textured
   full-body/face reconstruction is produced end-to-end.
3. Demonstrate stable private preview, customer correction/re-capture, deletion,
   operator review and file download.
4. Repair the mesh for a selected full-color print supplier and receive a
   physically printed sample with approved skin/outfit colors.
5. Establish real merchant, refund, shipping and support processes, including
   secure customer identities and verified payment webhooks.
6. Validate the end-to-end process on multiple people with different lighting,
   hairstyles and clothing.
7. Document test logs, sample photographs (only with permission), measurements,
   printer constraints and operator acceptance.

## Product claim policy

The active site must never:
- display a generic or AI-generated cartoon as a “real scanned preview”;
- claim a model succeeded when a GPU stage failed;
- claim a model is printer-approved based only on geometry export;
- present unverified payment/checkout states;
- guarantee 100% identical appearance from arbitrary phone images.
