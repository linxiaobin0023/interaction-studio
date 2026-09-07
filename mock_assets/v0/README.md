# Synthetic Mock Asset Pack v0.2

## Purpose

This pack is a development-only pilot for the Interaction Studio asset pipeline. It is designed to exercise upload, hashing, metadata, readiness checks, landmark detection, view selection and UI rendering before customer assets are available.

Every image is synthetic and must be labeled `SYNTHETIC_MOCK`. The character is fictional and is not intended to resemble a real person. The pacifier is an unbranded fictional SKU.

## Hard boundaries

- Dataset class: `DEVELOPMENT` only.
- Never import these files into `FORMAL` or use them to claim Formal readiness or pass rate.
- Never use this pack as evidence that customer identity, product geometry, material or deployment requirements have passed Preflight.
- The two Alpha product images are development cutouts, not proof of production material fidelity.
- The generated asset tool does not expose a reproducible API model snapshot in the artifact metadata; use this pack for plumbing and visual spikes only.

## Current contents

- Canonical character: front, left 45 degrees, right 45 degrees.
- Product: front, left/right 45 degrees, left/right profile, rear; front material references on white/gray/black.
- Alpha product: six views covering the measured Mock face/hand pose pairs, with verified RGBA pixels and SHA256.
- Case Base pilot: one Mouth, one Near-mouth and eight independent Hand-held cases, all without a pacifier.

This is a structural pilot, not the final Development/Validation quota. Hand now meets the eight-case G1 structural minimum. Mouth still needs nine additional independent bases before Repair evidence is attempted. Validation must be generated from separate prompts/seeds and stored in a separate manifest.

## Known limitations

- Cross-view geometry and identity are visually consistent but not physically measured ground truth.
- Chroma-key Alpha supports structural compositing, but the nipple has no usable internal partial Alpha. Preflight therefore records `Transmission/Specular required`; those layers are not fabricated by this pack.
- MediaPipe 0.10.35 detects 478 face points on 13/13 character/case images and 21 hand points on 8/8 Hand cases. This is development evidence, not anatomy approval for customer assets.
- Exact yaw/pitch values are prompt targets, not sensor measurements; a landmark estimator must write measured values separately.

See `metadata/asset_manifest.json` for hashes and declared metadata, `PROMPTS.md` for the exact generation prompt set, and `../../docs/preflight/` for model, residual and composite evidence.
