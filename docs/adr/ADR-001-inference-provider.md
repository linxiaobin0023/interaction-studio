# ADR-001: Inference provider and environment baseline

- Status: `PROVISIONAL_ACCEPTED_FOR_G2_BENCHMARK`
- Date: 2026-09-03
- Scope: image generation/editing provider only; CV landmarking, masks, compositing and evidence remain local services

## Decision

Use a provider-neutral `InferenceProvider` adapter and benchmark two pinned API candidates before freezing the Formal route:

1. Primary candidate: OpenAI `gpt-image-2-2026-04-21`.
2. Challenger: Black Forest Labs `flux-2-pro` fixed endpoint.
3. Local development fallback: FLUX.2 `[klein]` 4B under Apache 2.0. It is not Formal-eligible until it independently passes the same benchmark.
4. Optional heavy local challenger: `Qwen/Qwen-Image-Edit` under Apache 2.0, only when local-data requirements justify its larger deployment footprint.

Do not use `latest` or preview aliases in Validation/Frozen Build/Formal. Persist provider, model ID, snapshot/revision, region, request parameters, seed if honored, input hashes and original returned output.

## Why

- GPT Image 2 supports generation, editing, high-fidelity image inputs and a dated snapshot.
- FLUX.2 supports multi-reference editing; the vendor documents `flux-2-pro` as a fixed endpoint suitable for reproducibility.
- FLUX.2 `[klein]` 4B provides an Apache-2.0 local path and is documented to run at about 13 GB VRAM, making a 24 GB development GPU a practical baseline with headroom.
- Qwen-Image-Edit is a 20B local editing model with appearance and semantic editing, but its larger memory/operations footprint makes it a fallback rather than the default.

Official references:

- https://developers.openai.com/api/docs/models/gpt-image-2
- https://docs.bfl.ai/flux_2/flux2_overview
- https://docs.bfl.ai/flux_2/flux2_image_editing
- https://huggingface.co/Qwen/Qwen-Image-Edit

## Environment baseline

### API-first development and production

- Linux container host, 8 vCPU, 32 GB RAM, 200 GB NVMe minimum for API/Worker/PostgreSQL/Redis development.
- S3-compatible object storage with versioning; Formal environment additionally requires validated Object Lock.
- Outbound HTTPS allow-list for enabled providers; secrets injected by environment/secret manager.
- No generation GPU is required for the primary API route.

### Local model/CV worker

- Linux, NVIDIA driver and Container Toolkit.
- Recommended: one NVIDIA GPU with at least 24 GB VRAM, 16 vCPU, 64 GB RAM and 1 TB NVMe.
- The 24 GB recommendation targets FLUX.2 `[klein]` 4B plus CV/mask processing headroom. It does not imply that Qwen-Image-Edit 20B will fit without quantization, offload or a larger/multi-GPU host.

## G2 benchmark

Use a frozen non-Formal benchmark manifest with at least 12 distinct Case Bases: 5 Mouth, 3 Near-mouth and 4 Hand-held, covering frontal/left/right Green poses plus at least two Yellow-boundary cases. Provide the exact same canonical references, product views, masks and edit instructions to each candidate.

For each candidate record:

- Product, Interaction, Identity, Scene and Overall QC;
- product geometry drift and forbidden-region changes;
- contact/occlusion quality;
- same-input repeatability;
- latency, provider errors, output size and metadata completeness;
- whether the model/revision can be pinned and audited.

Selection order is: technical eligibility first, then repeatability and preservation, then latency. No candidate is selected solely because it generated the synthetic mock pack successfully.

## Data boundary

Until external-image processing is explicitly approved, only `SYNTHETIC_MOCK` assets may be sent to external APIs. Customer and Formal assets stay blocked at the adapter policy layer.
