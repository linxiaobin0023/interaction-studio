# Materials and development — 2026-09-05

Follow-up: `2026-09-05-model-independent-development.md` records the user's decision
to defer model integration and the delivered local preview workflow. This document
retains the earlier materials milestone.

State: `IN EXECUTION / INPUTS READY / G2 PREPARATION`.
Full implementation is not yet authorized by the frozen gates.

## Delivered inputs

| Dataset | Cases | Mouth | Near-mouth | Hand-held | Measured Green / Yellow | Face / Hand detection |
|---|---:|---:|---:|---:|---|---|
| Development v1 | 30/30 | 12 | 8 | 10 | 24 / 6 | 30/30 / 10/10 |
| Validation v1 | 20/20 | 8 | 5 | 7 | 16 / 4 | 20/20 / 7/7 |

Both inputs pass engineering admission and are locally hash-sealed. Validation was
sealed after input admission and before any production workflow parameter selection.
All 37 newly admitted case bases were generated with the Codex built-in image tool,
using the canonical fictional identity as the only image reference. Separate jobs
and prompts were used per case; no Development case was supplied to Validation.
Four Development and two Validation initial candidates missed the measured Yellow
zone and were replaced. Their original outputs and generation records are retained,
but they are excluded from the admitted manifests.

Exact prompts, returned image paths and selected job IDs are in each dataset's
generation/replacement JSON records and `PROMPTS.md`. All selected images are copied
into the project. There are no cross-dataset duplicate image hashes, prompt IDs or
generation job IDs. This is a provenance/hash check, not proof of semantic independence.
Identity and anatomy were visually reviewed as engineering input admission, not Formal QC.

## Development delivered

- Inventory completion is now `CANDIDATE_COMPLETE`; count alone cannot produce READY.
- `tools/admit_dataset.py` verifies actual image hashes, quotas, canonical identity
  reference, exact evidence coverage, pinned landmark models, measured pose zones,
  visual review and cross-dataset reuse before admission. It seals once and verifies
  all referenced local files; changed input rebuilding requires a new dataset version.
- `GET /api/v1/datasets/{development|validation}/release` returns aggregate counts,
  measured pose mix and seal verification. It does not return cases, prompts or paths.
  Missing/corrupt evidence fails closed; Formal is not an accepted endpoint value.
- Compose mounts only the required release artifact directories read-only.
- `tools/prepare_g2_benchmark.py` fixes 12 Development cases (5 Mouth, 3 Near-mouth,
  4 Hand-held), including 3 Yellow cases, with a 5-case × 5-repeat schedule and
  hash-bound product layers. All 12 selected residual pairs meet yaw ≤12° / pitch ≤8°.
  Hand product view selection uses palm geometry. No inference was performed.
- CI includes release seal verification and deterministic benchmark preparation.
  Its dependency installation now creates the `.venv` used by Make targets.

## Validation

- Full Python suite: **80 passed**, 3 warnings.
- `make lint`: passed.
- `make dataset-seals-verify`: both releases passed.
- `make g0-verify`: original G0 hashes and dataset plan passed.
- `make benchmark-prepare`: reproducible; no unresolved selected residual cases.
- `docker compose config -q`: passed.
- `docker compose build api`: passed (image manifest `sha256:8098293e4ac5137776b4af3b2e86cf7cc08897d0a5a26ad060fb8d32c9bfce49`).
- Packaged API container smoke check with the Compose read-only mounts: Development
  returned READY/30, Validation READY/20, and Formal access was rejected with HTTP 422.
  The temporary container was removed after the check; no persistent service was started.

## Remaining conditions

The input-count conditions from the original G0 decision are closed by
`docs/gates/input-readiness-2026-09-05.json`. The original G0 result remains intact.
This checkpoint does not claim a complete G1 or G2 pass.

G2 still requires a configured production provider project/credentials, pinned model
and region, a frozen contact-edit workflow with identical masks per provider, and
preregistered repeatability decision rules. No provider key is configured in the
current process, and no local `.env` exists. Built-in case generation is not a
substitute for that benchmark. Subsequent full workflow development remains subject
to the frozen Technical Preflight / G2 conditions.

The seals provide local integrity verification; they are not Object Lock, access
isolation from the workspace owner, a legal signature or Formal eligibility.
Formal remains unopened. No inference output quality/pass rate has been measured.

Useful commands:

```bash
make dataset-seals-verify
make benchmark-prepare
make lint test
make api-dev
# GET http://localhost:8000/api/v1/datasets/development/release
# GET http://localhost:8000/api/v1/datasets/validation/release
```
