"""Deterministic Alpha compositing spike driven by landmark evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def center(points: list[list[float]]) -> tuple[float, float]:
    return (
        sum(item[0] for item in points) / len(points),
        sum(item[1] for item in points) / len(points),
    )


def select_hand(candidates: list[dict]) -> dict:
    return min(
        candidates,
        key=lambda item: item["box_normalized"][1] + item["box_normalized"][3] * 0.5,
    )


def placement(case: dict, landmark: dict) -> tuple[float, float, float, str]:
    interaction = case.get("interaction")
    if interaction == "HAND_HELD":
        hand = select_hand(landmark["hand"]["candidates"])
        thumb_tip = hand["landmarks_normalized"][4]
        index_tip = hand["landmarks_normalized"][8]
        x, y = center([thumb_tip, index_tip])
        return x, y, 0.16, "HAND_THUMB_INDEX_MIDPOINT"

    corners = landmark["face"]["mouth_corners_normalized"]
    x, y = center(corners)
    if interaction == "NEAR_MOUTH":
        x += 0.105
        return x, y, 0.12, "MOUTH_CORNER_OFFSET"
    return x, y, 0.13, "MOUTH_CORNERS_MIDPOINT"


def choose_product(case_landmark: dict, products: list[dict]) -> tuple[dict, dict]:
    pose = case_landmark["face"]["measured_pose_degrees"]
    if "hand" in case_landmark:
        pose = select_hand(case_landmark["hand"]["candidates"])[
            "measured_grip_pose_degrees"
        ]
    target_yaw = float(pose["yaw"])
    target_pitch = float(pose["pitch"])
    product = min(
        products,
        key=lambda item: abs(target_yaw - float(item["view_yaw"]))
        / float(item["max_residual_yaw"])
        + abs(target_pitch - float(item["view_pitch"]))
        / float(item["max_residual_pitch"]),
    )
    residual = {
        "yaw": round(abs(target_yaw - float(product["view_yaw"])), 3),
        "pitch": round(abs(target_pitch - float(product["view_pitch"])), 3),
        "within_gate": (
            abs(target_yaw - float(product["view_yaw"]))
            <= float(product["max_residual_yaw"])
            and abs(target_pitch - float(product["view_pitch"]))
            <= float(product["max_residual_pitch"])
        ),
    }
    return product, residual


def alpha_material_decision(product_path: Path) -> dict:
    alpha = np.asarray(Image.open(product_path).convert("RGBA"))[:, :, 3]
    silhouette = (alpha > 0).astype(np.uint8)
    interior = cv2.erode(silhouette, np.ones((9, 9), np.uint8), iterations=1).astype(bool)
    partially_transparent = (alpha > 0) & (alpha < 255)
    interior_count = int(np.count_nonzero(interior))
    interior_partial_count = int(np.count_nonzero(partially_transparent & interior))
    ratio = interior_partial_count / interior_count if interior_count else 0.0
    required = ratio < 0.02
    return {
        "transmission_specular_required": required,
        "method": "ERODED_ALPHA_INTERIOR_COVERAGE",
        "interior_partial_alpha_ratio": round(ratio, 6),
        "decision_threshold": 0.02,
        "reason": (
            "RGBA is a cutout matte without sufficient internal transmission; "
            "retain explicit Transmission/Specular layers"
            if required
            else "RGBA contains sufficient internal partial alpha for the pilot composite"
        ),
    }


def run_composite_spike(
    manifest_path: Path,
    asset_root: Path,
    landmark_report_path: Path,
    output_dir: Path,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    landmarks_report = json.loads(landmark_report_path.read_text(encoding="utf-8"))
    manifest_hash = sha256_file(manifest_path)
    if landmarks_report.get("manifest_sha256") != manifest_hash:
        raise ValueError("landmark report does not match the asset manifest")

    landmarks = {item["asset_id"]: item for item in landmarks_report["assets"]}
    products = [
        item
        for item in manifest["assets"]
        if item["type"] == "PRODUCT_VIEW" and item.get("has_alpha")
    ]
    cases = [item for item in manifest["assets"] if item["type"] == "CASE_BASE"]
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_output in output_dir.glob("*.png"):
        stale_output.unlink()
    outputs = []
    for case in cases:
        evidence = landmarks[case["asset_id"]]
        product, residual = choose_product(evidence, products)
        x, y, width_ratio, anchor_method = placement(case, evidence)
        base = Image.open(asset_root / case["path"]).convert("RGBA")
        overlay = Image.open(asset_root / product["path"]).convert("RGBA")
        target_width = max(1, round(base.width * width_ratio))
        target_height = max(1, round(target_width * overlay.height / overlay.width))
        overlay = overlay.resize((target_width, target_height), Image.Resampling.LANCZOS)
        left = round(x * base.width - target_width / 2)
        top = round(y * base.height - target_height / 2)
        composed = base.copy()
        composed.alpha_composite(overlay, (left, top))
        output_path = output_dir / f"{case['asset_id'].lower()}__{product['asset_id'].lower()}.png"
        composed.convert("RGB").save(output_path, format="PNG", optimize=True)
        outputs.append(
            {
                "case_asset_id": case["asset_id"],
                "product_asset_id": product["asset_id"],
                "output_path": str(output_path),
                "output_sha256": sha256_file(output_path),
                "anchor_method": anchor_method,
                "center_normalized": [round(x, 6), round(y, 6)],
                "width_ratio": width_ratio,
                "residual": residual,
            }
        )

    front_alpha = min(products, key=lambda item: abs(float(item["view_yaw"])))
    return {
        "report_version": "1.0.0",
        "manifest_sha256": manifest_hash,
        "landmark_report_sha256": sha256_file(landmark_report_path),
        "composite_count": len(outputs),
        "outputs": outputs,
        "material_decision": alpha_material_decision(asset_root / front_alpha["path"]),
    }
