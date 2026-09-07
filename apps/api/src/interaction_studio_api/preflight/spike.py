import hashlib
from pathlib import Path

import cv2
import numpy as np

from ..domain.enums import AssetType, CheckStatus
from ..domain.manifests import AssetManifest, ManifestAsset
from ..domain.readiness import (
    ReadinessEvaluationRequest,
    evaluate_readiness,
    metadata,
    numeric_metadata,
)

PINNED_LANDMARK_MODEL_SHA256 = {
    "hand_landmarker.task": "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    "face_landmarker.task": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def normalized_face_measurement(image: np.ndarray, cascade) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return {"detected": False, "candidate_count": 0}

    x, y, width, height = max(faces, key=lambda box: int(box[2]) * int(box[3]))
    image_height, image_width = image.shape[:2]
    face_box = [
        round(int(x) / image_width, 6),
        round(int(y) / image_height, 6),
        round(int(width) / image_width, 6),
        round(int(height) / image_height, 6),
    ]
    mouth_center = [
        round((int(x) + int(width) * 0.5) / image_width, 6),
        round((int(y) + int(height) * 0.72) / image_height, 6),
    ]
    return {
        "detected": True,
        "candidate_count": len(faces),
        "selected_face_box_normalized": face_box,
        "template_mouth_center_normalized": mouth_center,
        "mouth_mode": "FACE_BOX_TEMPLATE",
    }


def as_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image[:, :, :3]


def corner_luma(image: np.ndarray) -> float:
    image = as_bgr(image)
    height, width = image.shape[:2]
    patch_height = max(1, height // 10)
    patch_width = max(1, width // 10)
    patches = [
        image[:patch_height, :patch_width],
        image[:patch_height, width - patch_width :],
        image[height - patch_height :, :patch_width],
        image[height - patch_height :, width - patch_width :],
    ]
    pixels = np.concatenate([patch.reshape(-1, patch.shape[-1]) for patch in patches])
    bgr = np.median(pixels[:, :3], axis=0)
    return round(float(0.114 * bgr[0] + 0.587 * bgr[1] + 0.299 * bgr[2]), 3)


def asset_image(root: Path, asset: ManifestAsset) -> tuple[Path | None, np.ndarray | None]:
    path = safe_path(root, asset.path)
    if path is None or not path.is_file():
        return path, None
    return path, cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


def trusted_report(report: dict | None, manifest_path_hash: str | None) -> bool:
    return bool(
        report
        and manifest_path_hash
        and report.get("manifest_sha256") == manifest_path_hash
    )


def trusted_landmark_report(report: dict | None, manifest_path_hash: str | None) -> bool:
    return bool(
        trusted_report(report, manifest_path_hash)
        and report.get("analyzer") == "MediaPipe Tasks Vision 0.10.35"
        and report.get("model_sha256") == PINNED_LANDMARK_MODEL_SHA256
    )


def landmark_index(report: dict | None) -> dict[str, dict]:
    if not report:
        return {}
    return {
        item["asset_id"]: item
        for item in report.get("assets", [])
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
    }


def composite_outputs_valid(report: dict | None, asset_root: Path) -> bool:
    if not report:
        return False
    project_root = asset_root.resolve().parent.parent
    for item in report.get("outputs", []):
        relative = item.get("output_path")
        expected_hash = item.get("output_sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            return False
        path = (project_root / relative).resolve()
        try:
            path.relative_to(project_root)
        except ValueError:
            return False
        if not path.is_file() or sha256_file(path) != expected_hash:
            return False
    return True


def pairwise_residuals(
    cases: list[ManifestAsset],
    products: list[ManifestAsset],
    landmarks: dict[str, dict],
) -> list[dict]:
    alpha_products = [asset for asset in products if bool(metadata(asset, "has_alpha"))]
    measurements = []
    for case in cases:
        evidence = landmarks.get(case.asset_id, {})
        pose = evidence.get("face", {}).get("measured_pose_degrees")
        pose_source = "FACE_TRANSFORMATION_MATRIX"
        if metadata(case, "interaction") == "HAND_HELD":
            hands = evidence.get("hand", {}).get("candidates", [])
            if hands:
                selected_hand = min(
                    hands,
                    key=lambda item: item["box_normalized"][1]
                    + item["box_normalized"][3] * 0.5,
                )
                pose = selected_hand.get("measured_grip_pose_degrees")
                pose_source = "HAND_PALM_NORMAL"
        if not pose or not alpha_products:
            continue
        target_yaw = float(pose["yaw"])
        target_pitch = float(pose["pitch"])
        candidates = []
        for product in alpha_products:
            view_yaw = numeric_metadata(product, "view_yaw")
            view_pitch = numeric_metadata(product, "view_pitch")
            max_yaw = numeric_metadata(product, "max_residual_yaw")
            max_pitch = numeric_metadata(product, "max_residual_pitch")
            if None in {view_yaw, view_pitch, max_yaw, max_pitch}:
                continue
            residual_yaw = abs(target_yaw - view_yaw)
            residual_pitch = abs(target_pitch - view_pitch)
            candidates.append(
                (
                    residual_yaw / max_yaw + residual_pitch / max_pitch,
                    product,
                    residual_yaw,
                    residual_pitch,
                    max_yaw,
                    max_pitch,
                )
            )
        if not candidates:
            continue
        _, product, residual_yaw, residual_pitch, max_yaw, max_pitch = min(
            candidates, key=lambda item: item[0]
        )
        measurements.append(
            {
                "case_asset_id": case.asset_id,
                "product_asset_id": product.asset_id,
                "product_pose_source": metadata(product, "pose_source")
                or "DECLARED_METADATA",
                "target_yaw": round(target_yaw, 3),
                "target_pitch": round(target_pitch, 3),
                "target_pose_source": pose_source,
                "residual_yaw": round(residual_yaw, 3),
                "residual_pitch": round(residual_pitch, 3),
                "max_residual_yaw": max_yaw,
                "max_residual_pitch": max_pitch,
                "within_gate": residual_yaw <= max_yaw and residual_pitch <= max_pitch,
            }
        )
    return measurements


def run_structural_preflight(
    manifest: AssetManifest,
    asset_root: Path,
    *,
    hand_in_core_scope: bool = True,
    include_side_views: bool = True,
    landmark_report: dict | None = None,
    composite_report: dict | None = None,
    anatomy_report: dict | None = None,
    manifest_sha256: str | None = None,
) -> dict:
    readiness = evaluate_readiness(
        ReadinessEvaluationRequest(
            manifest=manifest,
            hand_in_core_scope=hand_in_core_scope,
            include_side_views=include_side_views,
        )
    )
    cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )

    integrity_errors: list[str] = []
    face_measurements: list[dict] = []
    product_measurements: list[dict] = []
    background_luma: dict[str, float] = {}

    for asset in manifest.assets:
        path, image = asset_image(asset_root, asset)
        if path is None or image is None:
            integrity_errors.append(f"{asset.asset_id}: unreadable or unsafe path")
            continue
        if sha256_file(path) != asset.sha256:
            integrity_errors.append(f"{asset.asset_id}: sha256 mismatch")
        actual_height, actual_width = image.shape[:2]
        if (actual_width, actual_height) != (asset.width, asset.height):
            integrity_errors.append(f"{asset.asset_id}: dimension mismatch")

        if asset.type in {AssetType.CANONICAL_CHARACTER, AssetType.CASE_BASE}:
            bgr_image = as_bgr(image)
            measurement = normalized_face_measurement(bgr_image, cascade)
            face_measurements.append({"asset_id": asset.asset_id, **measurement})

        if asset.type in {AssetType.PRODUCT_VIEW, AssetType.MATERIAL_REFERENCE}:
            channel_count = 1 if image.ndim == 2 else image.shape[2]
            alpha_ratio = 0.0
            if channel_count == 4:
                alpha_ratio = float(np.mean(image[:, :, 3] < 255))
            measurement = {
                "asset_id": asset.asset_id,
                "channel_count": channel_count,
                "alpha_nonopaque_ratio": round(alpha_ratio, 6),
                "corner_luma": corner_luma(image),
                "declared_background": metadata(asset, "background"),
            }
            product_measurements.append(measurement)
            if metadata(asset, "view_yaw") == 0 and metadata(asset, "background"):
                background_luma[str(metadata(asset, "background"))] = measurement["corner_luma"]

    face_failures = [item["asset_id"] for item in face_measurements if not item["detected"]]
    ambiguous_faces = [
        item["asset_id"] for item in face_measurements if item.get("candidate_count", 0) > 1
    ]
    product_assets = [item for item in manifest.assets if item.type is AssetType.PRODUCT_VIEW]
    case_assets = [item for item in manifest.assets if item.type is AssetType.CASE_BASE]
    hand_assets = [
        item
        for item in case_assets
        if metadata(item, "interaction") == "HAND_HELD"
    ]
    transparent_products = [
        item for item in product_measurements if item["alpha_nonopaque_ratio"] > 0
    ]
    residual_metadata_complete = all(
        metadata(asset, "max_residual_yaw") is not None
        and metadata(asset, "max_residual_pitch") is not None
        for asset in product_assets
    )
    material_order_valid = (
        set(background_luma) >= {"WHITE", "GRAY", "BLACK"}
        and background_luma["WHITE"] > background_luma["GRAY"] > background_luma["BLACK"]
    )
    landmarks_trusted = trusted_landmark_report(landmark_report, manifest_sha256)
    landmarks = landmark_index(landmark_report) if landmarks_trusted else {}
    face_landmark_failures = [
        asset.asset_id
        for asset in [
            item
            for item in manifest.assets
            if item.type in {AssetType.CANONICAL_CHARACTER, AssetType.CASE_BASE}
        ]
        if not landmarks.get(asset.asset_id, {}).get("face", {}).get("detected")
        or landmarks.get(asset.asset_id, {}).get("face", {}).get("landmark_count", 0) < 468
    ]
    mouth_geometry_failures = [
        asset.asset_id
        for asset in case_assets
        if len(
            landmarks.get(asset.asset_id, {})
            .get("face", {})
            .get("mouth_corners_normalized", [])
        )
        != 2
        or len(
            landmarks.get(asset.asset_id, {})
            .get("face", {})
            .get("lip_polygon_normalized", [])
        )
        < 20
    ]
    hand_landmark_failures = []
    for asset in hand_assets:
        hand = landmarks.get(asset.asset_id, {}).get("hand", {})
        candidates = hand.get("candidates", [])
        if not hand.get("detected") or not any(
            item.get("landmark_count") == 21 for item in candidates
        ):
            hand_landmark_failures.append(asset.asset_id)

    residuals = pairwise_residuals(case_assets, product_assets, landmarks)
    residual_failures = [item["case_asset_id"] for item in residuals if not item["within_gate"]]
    residual_measurement_complete = (
        landmarks_trusted and len(residuals) == len(case_assets) and not residual_failures
    )
    unverified_product_pose_assets = sorted(
        {
            item["product_asset_id"]
            for item in residuals
            if item["product_pose_source"] == "GENERATION_TARGET_UNVERIFIED"
        }
    )
    composite_case_ids = {
        item.get("case_asset_id")
        for item in (composite_report or {}).get("outputs", [])
        if isinstance(item, dict)
    }
    composite_trusted = bool(
        trusted_report(composite_report, manifest_sha256)
        and composite_report.get("composite_count") == len(case_assets)
        and composite_case_ids == {asset.asset_id for asset in case_assets}
        and composite_outputs_valid(composite_report, asset_root)
    )
    material_decision_recorded = bool(
        composite_trusted
        and isinstance(
            composite_report.get("material_decision", {}).get(
                "transmission_specular_required"
            ),
            bool,
        )
    )
    anatomy_assets = {
        item.get("asset_id"): item.get("decision")
        for item in (anatomy_report or {}).get("assets", [])
        if isinstance(item, dict)
    }
    anatomy_trusted = bool(
        trusted_report(anatomy_report, manifest_sha256)
        and anatomy_report.get("scope") == "SYNTHETIC_MOCK_PILOT_ONLY"
        and anatomy_report.get("formal_eligible") is False
        and anatomy_assets == {asset.asset_id: "PASS" for asset in hand_assets}
    )

    checks = [
        {
            "check_id": "ASSET_INTEGRITY",
            "status": CheckStatus.PASS if not integrity_errors else CheckStatus.BLOCKED,
            "observed": {"errors": integrity_errors, "asset_count": len(manifest.assets)},
        },
        {
            "check_id": "FACE_DETECTION",
            "status": (
                CheckStatus.BLOCKED
                if (landmarks_trusted and face_landmark_failures)
                or (not landmarks_trusted and (face_failures or cascade.empty()))
                else (
                    CheckStatus.WARN
                    if not landmarks_trusted and ambiguous_faces
                    else CheckStatus.PASS
                )
            ),
            "observed": {
                "analyzer": (
                    landmark_report.get("analyzer")
                    if landmarks_trusted
                    else "OpenCV Haar frontal face"
                ),
                "detected": (
                    len(face_measurements) - len(face_landmark_failures)
                    if landmarks_trusted
                    else len(face_measurements) - len(face_failures)
                ),
                "total": len(face_measurements),
                "failed_assets": face_landmark_failures if landmarks_trusted else face_failures,
                "ambiguous_assets": [] if landmarks_trusted else ambiguous_faces,
            },
        },
        {
            "check_id": "MOUTH_GEOMETRY",
            "status": (
                CheckStatus.PASS
                if landmarks_trusted and not mouth_geometry_failures
                else CheckStatus.BLOCKED
            ),
            "observed": {
                "analyzer": landmark_report.get("analyzer") if landmarks_trusted else None,
                "mouth_mode": "FACE_LANDMARK" if landmarks_trusted else "UNAVAILABLE",
                "failed_assets": mouth_geometry_failures,
            },
        },
        {
            "check_id": "PRODUCT_ALPHA",
            "status": CheckStatus.PASS if transparent_products else CheckStatus.BLOCKED,
            "observed": {
                "transparent_product_count": len(transparent_products),
                "required": 1,
            },
        },
        {
            "check_id": "PRODUCT_RESIDUAL_METADATA",
            "status": (
                CheckStatus.BLOCKED
                if not residual_metadata_complete or not residual_measurement_complete
                else (
                    CheckStatus.WARN
                    if unverified_product_pose_assets
                    else CheckStatus.PASS
                )
            ),
            "observed": {
                "complete": residual_metadata_complete,
                "target_pose_measured": residual_measurement_complete,
                "product_pose_measured": not unverified_product_pose_assets,
                "pairwise_residual_evaluated": residual_measurement_complete,
                "pair_count": len(residuals),
                "failed_assets": residual_failures,
                "unverified_product_pose_assets": unverified_product_pose_assets,
            },
        },
        {
            "check_id": "MATERIAL_BACKGROUND_MEASUREMENT",
            "status": CheckStatus.PASS if material_order_valid else CheckStatus.BLOCKED,
            "observed": {"corner_luma": background_luma, "expected_order": "WHITE>GRAY>BLACK"},
        },
        {
            "check_id": "MATERIAL_LAYERING_DECISION",
            "status": CheckStatus.PASS if material_decision_recorded else CheckStatus.BLOCKED,
            "observed": (
                composite_report.get("material_decision")
                if material_decision_recorded
                else "Transmission/Specular necessity requires a trusted composite report"
            ),
        },
        {
            "check_id": "HAND_LANDMARK",
            "status": (
                CheckStatus.PASS
                if hand_in_core_scope
                and landmarks_trusted
                and len(hand_assets) >= 8
                and not hand_landmark_failures
                else (CheckStatus.WARN if not hand_in_core_scope else CheckStatus.BLOCKED)
            ),
            "observed": {
                "trusted_report": landmarks_trusted,
                "case_count": len(hand_assets),
                "detected_count": len(hand_assets) - len(hand_landmark_failures),
                "failed_assets": hand_landmark_failures,
            },
        },
        {
            "check_id": "HAND_ANATOMY_QC",
            "status": (
                CheckStatus.PASS
                if hand_in_core_scope and anatomy_trusted
                else (CheckStatus.WARN if not hand_in_core_scope else CheckStatus.BLOCKED)
            ),
            "observed": {
                "trusted_report": anatomy_trusted,
                "reviewer_type": (
                    anatomy_report.get("reviewer_type") if anatomy_trusted else None
                ),
                "case_count": len(anatomy_assets),
                "formal_eligible": False,
            },
        },
    ]
    blockers = [item["check_id"] for item in checks if item["status"] == CheckStatus.BLOCKED]
    blockers.extend(
        item for item in readiness.blocking_conditions if item not in blockers
    )

    return {
        "report_version": "0.2.0",
        "pack_id": manifest.pack_id,
        "scope_assumptions": {
            "hand_in_core_scope": hand_in_core_scope,
            "include_side_views": include_side_views,
        },
        "technical_status": "BLOCKED" if blockers else "CONDITIONAL",
        "readiness_status": readiness.readiness_status.value,
        "formal_gate_eligible": readiness.formal_gate_eligible,
        "checks": checks,
        "blocking_conditions": blockers,
        "raw_measurements": {
            "faces": face_measurements,
            "products": product_measurements,
            "pairwise_residuals": residuals,
            "landmark_model_sha256": (
                landmark_report.get("model_sha256") if landmarks_trusted else None
            ),
        },
        "gate_effect": "NONE" if not readiness.formal_gate_eligible else "UNSIGNED",
    }
