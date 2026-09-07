# Interaction Studio

Production implementation of the frozen person-pacifier interaction workflow. The repository contains the G0/G1 foundation, a hash-bound internal G0 decision, a deterministic parametric product master, complete and locally sealed Development/Validation inputs, the core API/data contracts and executable evidence validators.

## Scope guardrails

- `interaction_studio_prototype/` is a visual/interaction reference, not production code.
- `mock_assets/` is synthetic Development data and is never Formal-eligible.
- Formal behavior must be enforced by API, database and runner rules, not only by disabled UI controls.
- External image providers are disabled by default.

## Prototype alignment

The local Studio now opens on the production overview with the prototype's global navigation.
Case/asset browsing, the existing editor, cross-case result review and local task summaries share
one console. See [the UI correction and browser evidence](docs/delivery/prototype-alignment/README.md).
Model-dependent capabilities and unavailable production metrics are explicitly marked as unavailable.
For an SSH project, server-side verification and desktop preview are separate checks; see
[preview startup recovery and verification](docs/delivery/prototype-alignment/remote-preview.md).

## Local usable delivery

The user-confirmed local delivery keeps model integration deferred. Start with
[the handoff guide](docs/delivery/local-v1/README.md). Unique accounts, role enforcement,
offline evidence packages, encrypted backup and isolated restore are included.

```bash
python3 tools/install_local_studio.py
```

Initial credentials are written to `data/local-delivery/initial-login.txt` (owner-only access).
The installer preserves existing accounts and project data on upgrades.

## Developer quick start

```bash
cp .env.example .env
make manifest-verify
make dataset-plan-verify
make api-install
make test
make preflight
make db-migrate
make api-dev
```

Or start the local infrastructure and API:

```bash
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8000/` for the local Studio. It supports case selection, drag placement,
manual occlusion, preview downloads, PostgreSQL drafts, template versions, save history,
durable background rendering jobs and versioned five-dimension Development QC.
See `docs/development/studio-workbench.md` and `docs/development/studio-jobs-qc.md`.
The overall project is still in development.

API endpoints:

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/manifests/validate`
- `POST /api/v1/readiness/evaluations`
- `GET /api/v1/contracts/core-resources`
- `GET /api/v1/contracts/state-machines`
- `GET /api/v1/datasets/development/release`
- `GET /api/v1/datasets/validation/release`
- `GET /api/v1/development/catalog`
- `POST /api/v1/development/previews?format=bundle` (also `png` / `manifest`)
- `GET/PUT /api/v1/development/studio/drafts/{case_id}`
- `GET/POST /api/v1/development/studio/templates`
- `GET/POST /api/v1/development/studio/jobs`
- `GET /api/v1/development/studio/jobs/{job_id}`
- `GET /api/v1/development/studio/jobs/{job_id}/output?format=bundle`
- `POST /api/v1/development/studio/jobs/{job_id}/reviews`
- `POST /api/v1/contracts/attempt-transitions/validate`
- `POST /api/v1/contracts/formal-run-transitions/validate`

The OpenAPI 3.1 contract is available at `GET /openapi.json`. Alembic owns the database
schema; run `make db-check` after changing an ORM model to detect migration drift.
Python dependency resolution is constrained by `apps/api/constraints.lock`; update it only
with a tested migration/container rebuild.

## Current delivery status

- Plan status: `APPROVED FOR G0/G1`.
- G0 internal scope/input decision: `PASS_INTERNAL`.
- Authoritative product master: 11 exact camera views with RGBA, Depth, Normal, Transmission and Specular layers.
- Project-owned Development v1: 30/30 Case Bases (12 Mouth, 8 Near-mouth, 10 Hand-held), measured 24 Green / 6 Yellow, admitted and locally hash-sealed.
- Independent Validation v1: 20/20 Case Bases (8 Mouth, 5 Near-mouth, 7 Hand-held), measured 16 Green / 4 Yellow, admitted and locally hash-sealed before parameter selection. Formal remains unopened.
- Input admission verifies image/manifest hashes, quotas, measured poses, pinned landmarks, visual review and cross-dataset duplicate hashes/jobs. Inventory completeness alone does not confer READY.
- Release summary API verifies local seal references without returning case images or prompt content. Compose mounts only the required artifact directories read-only.
- G2 input plan: 12 fixed Development cases, 5-case × 5-repeat schedule and authoritative product-layer references; selected pairwise residuals pass. No provider execution or G2 decision has occurred.
- Synthetic pilot manifest: structurally and cryptographically verifiable.
- Core Dataset/Case/Attempt/Output/QC/Gate/FormalRun/Evidence schema: migration-backed.
- Attempt and FormalRun transitions: server-enforced and published in OpenAPI.
- Mock v0.2 readiness and structural CV preflight: 0 technical blockers, reproducible and explicitly `PILOT_ONLY`; MediaPipe runs in an isolated worker environment.
- Provider decision: provisional; see `docs/adr/ADR-001-inference-provider.md`.
- Model integration is deferred at the user's request. Model-free Development work continues:
  case catalog, automatic/manual placement, six masks, five product layers and downloadable
  preview bundles are implemented. Local coverage is 29 rendered / 1 residual-blocked case;
  these counts are not a quality pass rate.
- Full implementation remains gated by Technical Preflight and the pinned G2 provider benchmark; Development/Validation input-count conditions are now complete.

Current execution details: `docs/status/2026-09-05-local-delivery.md`.

Run `make local-preview CASE_ID=DEV_MOUTH_001` without any API key, GPU, database or queue.
Use `/docs` after `make api-dev` to adjust placement and download previews.
See `docs/development/local-preview-api.md` for mask semantics, examples and limitations.

Verify the admitted releases with `make dataset-seals-verify`; reproduce the G2 input plan
with `make benchmark-prepare`. Local runs resolve `ARTIFACT_ROOT` from the project directory;
Compose sets it to `/app/artifacts`. A local hash seal detects changes and is not S3 Object Lock.
New input changes require a new dataset version. The built-in generator constructs synthetic
inputs; it does not establish pinned model eligibility. Production credentials, a frozen edit
workflow/masks and preregistered repeatability rules are still needed for actual G2 execution.
