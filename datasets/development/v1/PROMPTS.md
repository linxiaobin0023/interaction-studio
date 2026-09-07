# Development v1 prompt and lineage record

Tool mode for newly generated cases: Codex built-in image generation. The built-in tool does not expose a reproducible API model snapshot, so these cases are Development-only until the G2 pinned-provider benchmark is available.

`DEV_MOUTH_001`, `DEV_NEAR_001`, and `DEV_HAND_001` through `DEV_HAND_008` were selected and promoted from Synthetic Mock v0.2. Their exact prompts remain in `mock_assets/v0/PROMPTS.md`; their source hashes are preserved by the snapshot manifest.

## DEV_MOUTH_002_V1

```text
Use case: photorealistic-natural
Asset type: PROJECT_OWNED_SYNTHETIC Development Case Base, prompt_id DEV_MOUTH_002_V1
Primary request: Create a new independent photorealistic static image of the exact same fictional toddler identity from Image 1, seated upright on a light oatmeal-colored floor cushion, with a relaxed closed mouth and unobstructed lips. No pacifier or product is present.
Input images: Image 1 is the authoritative identity reference; preserve face shape, hazel eyes, warm brown curls, age, skin tone, and muted-blue shirt. Do not copy its studio background or exact crop.
Scene/backdrop: bright minimal sunroom with warm off-white plaster wall, blurred indoor olive tree and pale woven rug.
Composition/framing: landscape 3:2, chest-up, centered face, both hands below the bottom edge, generous clear area around cheeks and mouth.
Lighting/mood: soft bounced morning daylight, neutral white balance, natural skin texture, calm expression.
Constraints: head yaw between -5 and +5 degrees, pitch within 5 degrees, roll within 3 degrees; lips fully visible and closed; anatomically natural; fictional identity only; no product, pacifier, food, bottle, hand near face, text, logo, or watermark.
Avoid: reused sofa/playroom/kitchen backgrounds, beauty retouching, motion blur, open mouth, teeth, tongue, facial occlusion, malformed anatomy.
```

## DEV_MOUTH_003_V1

```text
Use case: photorealistic-natural
Asset type: PROJECT_OWNED_SYNTHETIC Development Case Base, prompt_id DEV_MOUTH_003_V1
Primary request: Create a new independent photorealistic static image of the exact same fictional toddler identity from Image 1, standing beside a low pale-wood bookcase with a relaxed closed mouth and fully visible lips. No pacifier or product is present.
Input images: Image 1 is the authoritative identity reference; preserve face shape, hazel eyes, warm brown curls, age, skin tone, and muted-blue shirt. Do not copy the reference background or crop.
Scene/backdrop: quiet Scandinavian-style reading nook, cream wall, softly blurred picture books and a small linen armchair; clearly distinct from all playroom and sofa scenes.
Composition/framing: landscape 3:2, waist-up, child slightly right of center, hands resting below chest and away from face, mouth region sharp.
Lighting/mood: diffuse overcast window light from camera left, calm neutral expression, realistic skin and fabric texture.
Constraints: head yaw about -12 degrees, pitch within 6 degrees, roll within 4 degrees; closed lips, no face occlusion; exactly one fictional child; no pacifier, product, food, bottle, text, logo, or watermark.
Avoid: prior scene reuse, open mouth, teeth, tongue, hand-face overlap, extra limbs, motion blur, plastic skin.
```

## DEV_NEAR_002_V1

```text
Use case: photorealistic-natural
Asset type: PROJECT_OWNED_SYNTHETIC Development Case Base, prompt_id DEV_NEAR_002_V1
Primary request: Create a new independent photorealistic static image of the exact same fictional toddler identity from Image 1 at a small white breakfast table, with clear negative space immediately to the LEFT of the mouth for later near-mouth product placement. No pacifier or product is present.
Input images: Image 1 is the authoritative identity reference; preserve face shape, hazel eyes, warm brown curls, age, skin tone, and muted-blue shirt. Do not copy its studio setting.
Scene/backdrop: airy dining nook with a pale sage wall, blurred ceramic vase and soft linen curtain; no toys or sofa.
Composition/framing: landscape 3:2, waist-up, child placed slightly right of center; one hand rests flat on the table below shoulder level; face and mouth are unobstructed; placement space is not cropped.
Lighting/mood: soft late-morning window light, realistic skin, neutral calm attention.
Constraints: head yaw about +18 degrees, pitch within 6 degrees, roll within 4 degrees; closed relaxed lips; exactly one fictional child; no product, pacifier, utensil, food, bottle, text, logo, or watermark.
Avoid: hand near face, competing object in placement space, prior scene reuse, malformed hands, motion blur, open mouth, beauty retouching.
```

## 2026-09-05 completion

Exact prompts and returned job paths are in `generation-plan-2026-09-05.json`, `generation-results-2026-09-05.json` and `replacement-plan-2026-09-05.json`. Mouth 009–012 V1 were rejected for insufficient measured yaw; V2 files were admitted. Built-in generation constructs case inputs; it does not establish pinned provider eligibility. Original rejected images are retained outside the admitted case index.
