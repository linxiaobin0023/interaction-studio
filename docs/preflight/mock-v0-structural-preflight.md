# Mock v0.2 Structural Preflight

Status: `CONDITIONAL / PILOT_ONLY`  
Gate effect: `NONE`  
Input manifest SHA-256: `bdca61ee10f15c702d6b21a29a442a809025a993a9b8b353dd1b927f5983a65a`

This is Development-only evidence. It clears the synthetic toolchain's P0 technical blockers but cannot satisfy G0, real Development/Validation readiness, or any Formal gate.

## Reproduction

```bash
make api-install
make preflight
```

`make preflight` fetches pinned MediaPipe model bundles by verified SHA256 into an ignored cache, executes the isolated landmark worker, creates deterministic composites, and evaluates the bound reports.

## Result

| Check | Result | Observation |
|---|---|---|
| Asset integrity | PASS | 27/27 assets decoded; SHA256 and dimensions match |
| Face detection | PASS | MediaPipe 0.10.35, 13/13 detected, 478 points selected |
| Mouth geometry | PASS | 10/10 Case images have measured corners and lip polygons |
| Product Alpha | PASS | 6 product views have non-opaque Alpha |
| Pairwise residual | WARN | 10/10 pairs meet yaw≤12° and pitch≤8°; target pose is measured but generated product pose remains declared/unverified |
| Material backgrounds | PASS | WHITE 254.000 > GRAY 146.886 > BLACK 17.114 |
| Material layering decision | PASS | Internal partial-Alpha ratio 0.000000; retain explicit Transmission/Specular layers |
| Hand landmark | PASS | 8/8 independent Hand cases have a detected 21-point skeleton |

Blocking conditions: none. The single warning is intentionally retained; generated view labels are not physical pose ground truth.

## Adversarial corrections made

1. Hand residual initially used head pose. The evaluator now uses the normalized palm plane from wrist/index-MCP/pinky-MCP landmarks.
2. The first ±60° product view was generated in the wrong quadrant and removed from the manifest; the corrected `-60°/+15°` view is used.
3. Landmark reports are trusted only when the manifest hash, analyzer version, and both pinned model hashes match.
4. Composite evidence is trusted only when it covers the exact Case set and is bound to the same manifest hash.

Machine-readable evidence:

- `mock-v0-landmarks.json`: raw landmark points, face poses, palm poses, analyzer/model hashes.
- `mock-v0-composites.json`: output hashes, anchors, selected product views and residuals.
- `mock-v0-structural-preflight.json`: authoritative synthetic preflight result.
