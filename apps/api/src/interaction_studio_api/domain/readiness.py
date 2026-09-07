from collections import Counter

from pydantic import BaseModel, ConfigDict

from .enums import (
    AssetType,
    CheckStatus,
    DatasetKind,
    InteractionKind,
    ReadinessStatus,
)
from .manifests import AssetManifest, ManifestAsset


class ReadinessEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: AssetManifest
    hand_in_core_scope: bool = True
    include_side_views: bool = True


class ReadinessCheck(BaseModel):
    check_id: str
    status: CheckStatus
    required: str
    observed: str
    blocking_conditions: list[str]


class ReadinessEvaluationResponse(BaseModel):
    pack_id: str
    technical_status: CheckStatus
    readiness_status: ReadinessStatus
    formal_gate_eligible: bool
    checks: list[ReadinessCheck]
    blocking_conditions: list[str]


def metadata(asset: ManifestAsset, key: str):
    return (asset.model_extra or {}).get(key)


def numeric_metadata(asset: ManifestAsset, key: str) -> float | None:
    value = metadata(asset, key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def angle_covered(angles: list[float], target: float, tolerance: float = 5) -> bool:
    return any(abs(angle - target) <= tolerance for angle in angles)


def check(
    check_id: str,
    passed: bool,
    *,
    required: str,
    observed: str,
    warning_only: bool = False,
) -> ReadinessCheck:
    status = CheckStatus.PASS
    if not passed:
        status = CheckStatus.WARN if warning_only else CheckStatus.BLOCKED
    return ReadinessCheck(
        check_id=check_id,
        status=status,
        required=required,
        observed=observed,
        blocking_conditions=[] if passed or warning_only else [check_id],
    )


def evaluate_readiness(request: ReadinessEvaluationRequest) -> ReadinessEvaluationResponse:
    manifest = request.manifest
    canonical = [asset for asset in manifest.assets if asset.type is AssetType.CANONICAL_CHARACTER]
    products = [asset for asset in manifest.assets if asset.type is AssetType.PRODUCT_VIEW]
    material_refs = [
        asset for asset in manifest.assets if asset.type is AssetType.MATERIAL_REFERENCE
    ]
    cases = [asset for asset in manifest.assets if asset.type is AssetType.CASE_BASE]

    canonical_yaws = [
        value
        for asset in canonical
        if (value := numeric_metadata(asset, "declared_yaw")) is not None
    ]
    product_yaws = [
        value
        for asset in products
        if (value := numeric_metadata(asset, "view_yaw")) is not None
    ]
    required_canonical_yaws = [0, -45, 45]
    required_product_yaws = [0, -45, 45, 180]
    if request.include_side_views:
        required_product_yaws.extend([-90, 90])

    case_counts = Counter(str(metadata(asset, "interaction")) for asset in cases)
    pose_counts = Counter(str(metadata(asset, "declared_pose_zone")) for asset in cases)
    non_green_count = pose_counts["YELLOW"] + pose_counts["RED"]
    non_green_ratio = non_green_count / len(cases) if cases else 1.0

    material_assets = [*products, *material_refs]
    material_backgrounds = {
        str(metadata(asset, "background"))
        for asset in material_assets
        if metadata(asset, "material_class") == "TRANSLUCENT"
        and (yaw := numeric_metadata(asset, "view_yaw")) is not None
        and angle_covered([yaw], 0)
    }
    alpha_count = sum(bool(metadata(asset, "has_alpha")) for asset in products)

    checks = [
        check(
            "CANONICAL_VIEW_COVERAGE",
            all(angle_covered(canonical_yaws, yaw) for yaw in required_canonical_yaws),
            required="front, left 45°, right 45°",
            observed=f"declared yaw={sorted(canonical_yaws)}",
        ),
        check(
            "PRODUCT_VIEW_COVERAGE",
            all(angle_covered(product_yaws, yaw) for yaw in required_product_yaws),
            required=f"declared yaw={sorted(required_product_yaws)}",
            observed=f"declared yaw={sorted(product_yaws)}",
        ),
        check(
            "PRODUCT_ALPHA_REQUIRED",
            alpha_count >= 1,
            required="at least one transparent product PNG",
            observed=f"has_alpha assets={alpha_count}",
        ),
        check(
            "MATERIAL_BACKGROUND_COVERAGE",
            {"WHITE", "GRAY", "BLACK"}.issubset(material_backgrounds),
            required="front translucent reference on WHITE, GRAY and BLACK",
            observed=f"backgrounds={sorted(material_backgrounds)}",
        ),
        check(
            "MOUTH_BASE_COVERAGE",
            case_counts[InteractionKind.MOUTH.value] >= 1,
            required="at least 1 Development mouth Base Case for structural spike",
            observed=f"cases={case_counts[InteractionKind.MOUTH.value]}",
        ),
        check(
            "NEAR_MOUTH_BASE_COVERAGE",
            case_counts[InteractionKind.NEAR_MOUTH.value] >= 1,
            required="at least 1 Development near-mouth Base Case for structural spike",
            observed=f"cases={case_counts[InteractionKind.NEAR_MOUTH.value]}",
        ),
        check(
            "HAND_BASE_COVERAGE",
            not request.hand_in_core_scope or case_counts[InteractionKind.HAND_HELD.value] >= 8,
            required="at least 8 Hand Development Base Cases when Hand is core scope",
            observed=f"cases={case_counts[InteractionKind.HAND_HELD.value]}",
        ),
        check(
            "POSE_DISTRIBUTION",
            pose_counts["RED"] == 0 and non_green_ratio <= 0.2,
            required="Red=0 and Yellow+Red <=20%",
            observed=(
                f"Red={pose_counts['RED']}, Yellow+Red={non_green_count}/{len(cases)} "
                f"({non_green_ratio:.1%})"
            ),
        ),
        check(
            "MATERIAL_LAYERING_DECISION",
            False,
            required="Preflight records whether Transmission/Specular layers are required",
            observed="not yet measured",
            warning_only=True,
        ),
    ]

    formal_gate_eligible = (
        manifest.formal_eligible
        and manifest.provenance != "SYNTHETIC_MOCK"
        and manifest.dataset is DatasetKind.FORMAL
    )
    checks.append(
        check(
            "FORMAL_PROVENANCE",
            formal_gate_eligible,
            required="non-synthetic provenance explicitly eligible for Formal",
            observed=(
                f"provenance={manifest.provenance}, formal_eligible={manifest.formal_eligible}"
            ),
            warning_only=True,
        )
    )

    blocking_conditions = [
        blocker for item in checks for blocker in item.blocking_conditions
    ]
    if blocking_conditions:
        technical_status = CheckStatus.BLOCKED
    elif any(item.status is CheckStatus.WARN for item in checks):
        technical_status = CheckStatus.WARN
    else:
        technical_status = CheckStatus.PASS

    if not formal_gate_eligible:
        readiness_status = ReadinessStatus.PILOT_ONLY
    elif blocking_conditions:
        readiness_status = ReadinessStatus.BLOCKED
    else:
        readiness_status = ReadinessStatus.PASS

    return ReadinessEvaluationResponse(
        pack_id=manifest.pack_id,
        technical_status=technical_status,
        readiness_status=readiness_status,
        formal_gate_eligible=formal_gate_eligible,
        checks=checks,
        blocking_conditions=blocking_conditions,
    )
