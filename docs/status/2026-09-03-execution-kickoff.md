# Execution kickoff status — 2026-09-03

## Outcome

- Project state: `IN EXECUTION`.
- G0 internal gate: `PASS_INTERNAL`; evidence hashes verified.
- Full-implementation transition: not yet allowed.
- Automated tests: 55 passed.

## Delivered in this increment

1. Frozen scope, metrics, project-owned synthetic provenance, data boundary, roles and P1 deferrals.
2. Dataset plan for 30 Development, 20 Validation, 24 Formal and 12 Generalization cases, with cross-dataset independence and sealing rules.
3. Deterministic SDF product master v1 with 11 exact camera poses and 55 hash-bound RGBA/Depth/Normal/Transmission/Specular outputs.
4. Development v1 snapshot at 13/30 cases: Mouth 3, Near-mouth 2, Hand-held 8.
5. Landmark evidence: Face 13/13; Hand 8/8.

## Remaining before full implementation

| Condition | Current | Required | Remaining |
|---|---:|---:|---:|
| Development Mouth | 3 | 12 | 9 |
| Development Near-mouth | 2 | 8 | 6 |
| Development Hand-held | 8 | 10 | 2 |
| Validation total | 0 | 20 | 20 |
| Pinned G2 provider benchmark | unavailable | available | provider project/credentials |

Formal remains unopened by design and will not be generated or inspected until the Validation/Frozen Build boundary is in place.

## Next execution slice

Generate the remaining 17 Development cases in independent scene/prompt jobs, run identity/landmark/anatomy admission, freeze Development v1, then generate and immediately seal the independent Validation v1 dataset. G2 provider benchmarking starts as soon as a production API project is available; until then built-in generation is limited to Development asset construction.
