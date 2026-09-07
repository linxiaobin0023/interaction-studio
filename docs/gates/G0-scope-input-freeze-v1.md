# G0 Scope / Input Boundary Freeze v1

Decision: `PASS_INTERNAL`  
Owner: `CODEX_PROJECT_LEAD`  
Date: 2026-09-03

## Frozen decisions

- Product scope is one project-owned fictional character, one project-owned fictional pacifier SKU and three static-image interactions: Mouth, Near-mouth and Hand-held.
- Hand remains a core Formal interaction.
- Authoritative inputs may be synthetic; “authoritative” means frozen project input, not customer photography.
- Technical Pass requires Product, Interaction, Identity, Scene and Overall to all pass.
- Production Pass additionally requires total human time at or below 180 seconds per case.
- Pose mix is at least 80% Green, at most 20% Yellow and zero Red.
- The product material class is Translucent. Transmission/Specular layers remain required.
- External inference currently accepts only `SYNTHETIC_MOCK` or `PROJECT_OWNED_SYNTHETIC`. Any future real-person/customer asset is local-only unless an approved ZDR project is recorded.
- All P1 enhancements remain Deferred. TCO/ROI is not a product feature or development-plan gate.

The machine-readable source of truth is `config/gates/g0-scope-freeze-v1.json`. A hash-bound gate result will be emitted after the product-master and dataset-registry inputs are created.

## Authority boundary

`CODEX_PROJECT_LEAD` owns execution, technical decisions, dataset custody and technical gates. The workspace owner remains the legal/billing authority because credentials, payment commitments and contracts require an external account holder.
