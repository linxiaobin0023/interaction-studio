# Generation prompt set

Tool path: Codex built-in image generation. Generation date: 2026-09-03. The built-in artifact did not expose an API model snapshot, so `model_revision` is recorded as `UNAVAILABLE_BUILTIN`.

## Shared character specification

`photorealistic-natural`; a completely fictional toddler around two years old; warm light-brown wavy hair, hazel eyes, fair-to-medium natural skin, plain muted-blue top; no resemblance to a known or real person; no pacifier, bottle, food, logo, text or watermark; accurate natural anatomy and unobstructed mouth.

- `character_front_00`: warm-gray studio, front view, yaw/pitch/roll 0, neutral closed mouth, head and upper torso.
- `character_left45_00`: edit from front reference; exact identity; child-left yaw 45 degrees; otherwise unchanged.
- `character_right45_00`: edit from front reference; exact identity; child-right yaw 45 degrees; otherwise unchanged.

## Shared product specification

`product-mockup`; one fictional unbranded pacifier; symmetrical muted sage-green shield with two ventilation holes, circular pull ring, colorless semi-translucent silicone nipple; realistic child-safe geometry; neutral catalog light; no person, hand, packaging, logo, text or watermark.

- `pacifier_front_white_00`: front orthographic-like catalog view on white.
- `pacifier_left45_white_00` / `pacifier_right45_white_00`: identity-preserving physical rotation to yaw -45/+45 degrees.
- `pacifier_left90_white_00` / `pacifier_right90_white_00`: strict left/right product profiles.
- `pacifier_back_white_00`: strict rear view showing nipple and rear shield geometry.
- `pacifier_front_gray_00` / `pacifier_front_black_00`: change only the background/material interaction while preserving the front product.

## Shared Case Base specification

`identity-preserve`; exact fictional canonical identity; correct scene, pose and framing before product insertion; no pacifier or competing object; `SYNTHETIC_MOCK`; Development only.

- `mouth_dev_001`: beige sofa, frontal Green pose, clear closed mouth, hands out of frame.
- `near_dev_001`: light wood table, target yaw about -25 degrees, clear negative space beside the mouth, hand below face.
- `hand_dev_001`: playroom, target yaw about +20 degrees, raised empty right-hand grip at chest level, face unobstructed.

All prompts also required photorealistic texture, sharp target regions, no motion blur and a 4:3 landscape Case Base composition.

## v0.2 exact prompts

The following prompts are recorded verbatim. Hand generations referenced `character_front_00.png` as Image 1 and `hand_dev_001.png` as Image 2.

### HAND_DEV_002

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_002
Primary request: Create a new, distinct photorealistic photograph of the same fictional toddler identity from Image 1. The toddler is seated at a small wooden activity table and raises one hand at chest height, making a natural open pinch/grip gesture with thumb and index finger separated, ready to hold a small object. No object is present.
Input images: Image 1 is the identity reference and must be preserved; Image 2 is only a hand-visibility and grip-gesture reference. Do not copy Image 2's room or exact pose.
Scene/backdrop: softly lit playroom with pale neutral wall and a few defocused wooden toys.
Composition/framing: landscape 4:3, waist-up, face and the entire raised hand including wrist, palm, thumb, index and middle fingers fully visible; no cropping of fingers; raised hand separated from face and body for landmark detection.
Lighting/mood: soft natural daylight, realistic skin texture, neutral color.
Constraints: same face, hair, eye color, age and blue shirt as identity reference; head yaw within 15 degrees and pitch within 8 degrees; anatomically correct hands with exactly five fingers; no pacifier, no product, no object in either hand.
Avoid: extra fingers, fused fingers, duplicate hands, occluded wrist, hand touching face, text, logos, watermark, artificial studio backdrop.
```

### HAND_DEV_003

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_003
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1, standing beside a low nursery shelf and raising the LEFT hand at shoulder height in a relaxed C-shaped grip pose, with thumb opposite the four fingers and no object present.
Input images: Image 1 is the identity reference and must be preserved; Image 2 is only a hand visibility reference, not a scene to copy.
Scene/backdrop: warm nursery, cream wall, defocused books and wooden blocks, visibly different layout from Image 2.
Composition/framing: landscape 4:3, waist-up, face and entire raised left hand and wrist visible, fingers separated from face and torso for landmark detection.
Lighting/mood: diffuse window light, natural skin.
Constraints: same face, curly brown hair, brown eyes, age and blue shirt; head yaw about -12 degrees, pitch under 8 degrees; exactly five anatomically correct fingers; no pacifier, product, toy, or object in the raised hand.
Avoid: extra/fused fingers, cropped wrist, hand-face overlap, text, logo, watermark.
```

### HAND_DEV_004

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_004
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1 seated in a simple high chair, raising the RIGHT hand in front of the shoulder with palm three-quarter toward camera and thumb/index forming a wide pinch ready to hold an object; no object is present.
Input images: Image 1 is the identity reference; Image 2 is hand visibility guidance only.
Scene/backdrop: bright family kitchen with pale cabinets and soft background blur; do not copy either reference backdrop.
Composition/framing: landscape 4:3, waist-up, entire right hand from wrist through fingertips isolated against an uncluttered pale area; other hand resting low.
Lighting/mood: soft morning daylight, neutral white balance.
Constraints: preserve identity, hair, eyes, age and blue shirt; head yaw about +10 degrees; exactly five correct fingers; no pacifier, product, food, utensil or held object.
Avoid: finger defects, duplicated limb, cropped hand, hand overlapping face, text, logos, watermark.
```

### HAND_DEV_005

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_005
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1 on a covered garden patio, raising the LEFT hand near chest level with wrist rotated slightly outward and thumb/index/middle fingers clearly visible in a natural tripod grip pose; no object present.
Input images: Image 1 defines identity; Image 2 provides only scale and hand clarity guidance.
Scene/backdrop: shaded patio, softly blurred greenery and light stone wall, no indoor furniture from references.
Composition/framing: landscape 4:3, waist-up, whole raised hand and wrist fully inside frame and separated from clothing.
Lighting/mood: soft open shade, realistic skin, calm expression.
Constraints: same identity and blue shirt; near-frontal head, yaw under 15 degrees; exactly five anatomically correct fingers; no pacifier, product, flower, toy or object in hand.
Avoid: extra fingers, fused fingertips, hand occlusion, harsh shadows, text, logo, watermark.
```

### HAND_DEV_006

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_006
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1 sitting on a neutral woven rug, raising the RIGHT hand at chest height with palm mostly facing camera and thumb/index in a narrow precision pinch, all fingers visible, no object.
Input images: Image 1 defines identity; Image 2 only demonstrates hand separation and visibility.
Scene/backdrop: calm reading corner with pale wall and blurred low bookshelf, composition different from references.
Composition/framing: landscape 4:3, knees-to-head framing, full right wrist, palm, thumb, index and all fingertips clearly within frame, hand away from face.
Lighting/mood: soft side daylight, photorealistic.
Constraints: preserve same face, curls, brown eyes, age and blue shirt; head yaw around +20 degrees, pitch under 10; exactly five correct fingers; no pacifier or held object.
Avoid: extra/fused fingers, cropped hand, hidden wrist, hand-face overlap, text, logos, watermark.
```

### HAND_DEV_007

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_007
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1 beside a bright window bench, raising the LEFT hand with palm in side profile and thumb/index forming an open circular grip pose, no object present.
Input images: Image 1 defines identity; Image 2 is only reference for hand clarity.
Scene/backdrop: window bench with soft gray cushion and distant blurred city garden, not the reference rooms.
Composition/framing: landscape 4:3, waist-up, entire left forearm and hand visible against a plain light background; fingers separated and not overlapping the face.
Lighting/mood: diffused overcast daylight, realistic skin.
Constraints: same identity and blue shirt; head yaw about -25 degrees but still Green pose; exactly five anatomically correct fingers; no pacifier, product or object.
Avoid: duplicate hands, extra digits, fused digits, hand crop, face occlusion, text, logos, watermark.
```

### HAND_DEV_008

```text
Use case: photorealistic-natural
Asset type: synthetic Development Hand Base Case, variant HAND_DEV_008
Primary request: Create a new distinct photorealistic photograph of the same fictional toddler identity from Image 1 standing near a pale blue playroom wall, raising the RIGHT hand below chin level with the wrist turned inward and thumb, index and middle forming a natural three-point grip pose, empty hand.
Input images: Image 1 is identity reference; Image 2 only informs hand scale and full visibility.
Scene/backdrop: minimal pale blue playroom wall with one softly blurred wooden mobile, different from prior scenes.
Composition/framing: landscape 4:3, waist-up, full raised hand including wrist and all fingertips visible and spatially separated from face and shirt.
Lighting/mood: even natural daylight, calm neutral expression.
Constraints: preserve same fictional child identity, curly brown hair, brown eyes, age and blue shirt; near frontal head with slight downward pitch; exactly five correct fingers; no pacifier, product or object.
Avoid: malformed hands, extra fingers, fused fingers, cropped wrist, hand touching face, text, logos, watermark.
```

### SKU_MOCK_FRONT_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development transparent product source
Primary request: Recreate the exact same pacifier from Image 1, preserving its front view, silhouette, proportions, sage-green color, ring, shield, center button, and translucent clear nipple, but place it on a perfectly flat solid #ff00ff chroma-key background for background removal.
Input images: Image 1 is the product identity and geometry reference; preserve the product exactly.
Scene/backdrop: one uniform #ff00ff color covering every background pixel, including the two ventilation holes and ring opening.
Composition/framing: centered front orthographic catalog view, same scale as source, generous padding, full product visible.
Lighting/mood: preserve soft neutral product highlights only.
Materials/textures: preserve matte translucent sage silicone/plastic and clear translucent nipple.
Constraints: change only the background; no floor plane, no cast shadow, no contact shadow, no reflection; do not use #ff00ff in the product; crisp antialiased product edges.
Avoid: geometry changes, color shifts, opaque nipple, background gradients, texture, text, logos, watermark.
```

### SKU_MOCK_RIGHT15_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_RIGHT15
Primary request: Create the exact same fictional sage-green pacifier shown in Images 1 and 2 at a precise intermediate product yaw of +15 degrees toward the right, preserving the physical geometry, silhouette, ring, shield, ventilation holes, center button, muted sage color and clear silicone nipple.
Input images: Image 1 is the exact front identity/geometry reference; Image 2 is the exact +45-degree rotation reference. Interpolate only the physical viewing angle to +15 degrees; do not redesign the product.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key background across every background pixel, including holes and ring opening.
Composition/framing: centered orthographic-like catalog view, same product scale and padding as references, full product visible.
Lighting/mood: soft neutral catalog highlights on product only.
Materials/textures: preserve matte translucent sage shield/ring and colorless semi-translucent nipple.
Constraints: no floor plane, cast shadow, contact shadow, reflection, text, logo or watermark; no #ff00ff on the product; crisp antialiased edges.
Avoid: geometry changes, front view, 45-degree view, color shift, opaque nipple, gradients, textures, cropped product.
```

Both chroma sources were converted with the bundled `remove_chroma_key.py` helper using border auto-key, soft matte, transparent threshold 12, opaque threshold 220 and despill. This conversion creates cutout Alpha only; it does not synthesize physical transmission.

### SKU_MOCK_RIGHT30_UP15_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_RIGHT30_UP15
Primary request: Recreate the exact same fictional sage-green pacifier from the references at product yaw +30 degrees right and pitch +15 degrees upward, preserving geometry, shield, ring, holes, button, color, and clear nipple.
Input images: Image 1 fixes product identity/front geometry; Image 2 fixes the right-side rotation direction. Change only viewing yaw/pitch.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key across every background pixel, holes and ring opening.
Composition/framing: centered orthographic-like catalog view, full product, generous padding.
Lighting/mood: soft neutral catalog highlights.
Materials/textures: matte translucent sage product with colorless semi-translucent nipple.
Constraints: exact yaw +30 and pitch +15; no floor, cast/contact shadow, reflection, text, logo, watermark, or magenta on product; crisp edges.
Avoid: redesign, wrong angle, color shift, opaque nipple, gradient, crop.
```

### SKU_MOCK_RIGHT45_UP15_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_RIGHT45_UP15
Primary request: Recreate the exact same fictional sage-green pacifier from the references at product yaw +45 degrees right and pitch +15 degrees upward, preserving geometry, shield, ring, holes, button, color, and clear nipple.
Input images: Image 1 fixes product identity/front geometry; Image 2 fixes the exact +45 right yaw. Add only +15 pitch upward.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key across every background pixel, holes and ring opening.
Composition/framing: centered orthographic-like catalog view, full product, generous padding.
Lighting/mood: soft neutral catalog highlights.
Materials/textures: matte translucent sage product with colorless semi-translucent nipple.
Constraints: exact yaw +45 and pitch +15; no floor, cast/contact shadow, reflection, text, logo, watermark, or magenta on product; crisp edges.
Avoid: redesign, wrong angle, color shift, opaque nipple, gradient, crop.
```

### SKU_MOCK_LEFT30_UP15_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_LEFT30_UP15
Primary request: Recreate the exact same fictional sage-green pacifier from the references at product yaw -30 degrees left and pitch +15 degrees upward, preserving geometry, shield, ring, holes, button, color, and clear nipple.
Input images: Image 1 fixes product identity/front geometry; Image 2 fixes the left-side rotation direction. Change only viewing yaw/pitch.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key across every background pixel, holes and ring opening.
Composition/framing: centered orthographic-like catalog view, full product, generous padding.
Lighting/mood: soft neutral catalog highlights.
Materials/textures: matte translucent sage product with colorless semi-translucent nipple.
Constraints: exact yaw -30 and pitch +15; no floor, cast/contact shadow, reflection, text, logo, watermark, or magenta on product; crisp edges.
Avoid: redesign, wrong angle, color shift, opaque nipple, gradient, crop.
```

### Rejected wrong-quadrant spike (not in manifest)

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_RIGHT60_DOWN15
Primary request: Recreate the exact same fictional sage-green pacifier from the references at product yaw +60 degrees right and pitch -15 degrees downward, preserving geometry, shield, ring, holes, button, color, and clear nipple.
Input images: Image 1 fixes +45 identity/geometry and Image 2 fixes +90 profile direction. Interpolate yaw to +60 and change pitch only to -15.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key across every background pixel, holes and ring opening.
Composition/framing: centered orthographic-like catalog view, full product, generous padding.
Lighting/mood: soft neutral catalog highlights.
Materials/textures: matte translucent sage product with colorless semi-translucent nipple.
Constraints: exact yaw +60 and pitch -15; no floor, cast/contact shadow, reflection, text, logo, watermark, or magenta on product; crisp edges.
Avoid: redesign, wrong angle, color shift, opaque nipple, gradient, crop.
```

This spike was rejected after the palm-normal convention was corrected and is retained only under ignored `tmp/imagegen/` for audit/debugging.

### SKU_MOCK_LEFT60_UP15_ALPHA_00 chroma source

```text
Use case: background-extraction
Asset type: synthetic Development product view, variant SKU_MOCK_LEFT60_UP15
Primary request: Recreate the exact same fictional sage-green pacifier from the references at product yaw -60 degrees left and pitch +15 degrees upward, preserving geometry, shield, ring, holes, button, color, and clear nipple.
Input images: Image 1 fixes -45 identity/geometry and Image 2 fixes -90 profile direction. Interpolate yaw to -60 and change pitch only to +15.
Scene/backdrop: perfectly flat uniform #ff00ff chroma-key across every background pixel, holes and ring opening.
Composition/framing: centered orthographic-like catalog view, full product, generous padding.
Lighting/mood: soft neutral catalog highlights.
Materials/textures: matte translucent sage product with colorless semi-translucent nipple.
Constraints: exact yaw -60 and pitch +15; no floor, cast/contact shadow, reflection, text, logo, watermark, or magenta on product; crisp edges.
Avoid: redesign, wrong angle, color shift, opaque nipple, gradient, crop.
```
