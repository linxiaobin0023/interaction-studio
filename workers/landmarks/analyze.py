"""Run pinned MediaPipe Face/Hand Landmarker models and emit auditable JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image

HAND_INTERACTION = "HAND_HELD"
FACE_ASSET_TYPES = {"CANONICAL_CHARACTER", "CASE_BASE"}
LIP_CONTOUR = [
    61,
    146,
    91,
    181,
    84,
    17,
    314,
    405,
    321,
    375,
    291,
    308,
    324,
    318,
    402,
    317,
    14,
    87,
    178,
    88,
    95,
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def point(landmark) -> list[float]:
    return [round(float(landmark.x), 6), round(float(landmark.y), 6), round(float(landmark.z), 6)]


def load_image(path: Path) -> mp.Image:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


def normalized_box(landmarks) -> list[float]:
    xs = [float(item.x) for item in landmarks]
    ys = [float(item.y) for item in landmarks]
    return [
        round(min(xs), 6),
        round(min(ys), 6),
        round(max(xs) - min(xs), 6),
        round(max(ys) - min(ys), 6),
    ]


def matrix_pose(matrix) -> dict[str, float]:
    rotation = np.asarray(matrix, dtype=float)[:3, :3]
    pitch = math.degrees(math.atan2(rotation[2, 1], rotation[2, 2]))
    yaw = math.degrees(
        math.atan2(-rotation[2, 0], math.sqrt(rotation[2, 1] ** 2 + rotation[2, 2] ** 2))
    )
    roll = math.degrees(math.atan2(rotation[1, 0], rotation[0, 0]))
    return {
        "yaw": round(yaw, 3),
        "pitch": round(pitch, 3),
        "roll": round(roll, 3),
        "method": "FACE_TRANSFORMATION_MATRIX_EULER_XYZ",
    }


def hand_plane_pose(landmarks) -> dict[str, float]:
    points = np.asarray([[item.x, item.y, item.z] for item in landmarks], dtype=float)
    normal = np.cross(points[5] - points[0], points[17] - points[0])
    norm = float(np.linalg.norm(normal))
    if norm == 0:
        raise ValueError("degenerate hand plane")
    normal /= norm
    if normal[2] > 0:
        normal *= -1
    yaw = math.degrees(math.atan2(normal[0], abs(normal[2])))
    pitch = math.degrees(math.atan2(normal[1], abs(normal[2])))
    return {
        "yaw": round(yaw, 3),
        "pitch": round(pitch, 3),
        "method": "PALM_NORMAL_WRIST_INDEX_MCP_PINKY_MCP",
    }


def create_detectors(model_dir: Path):
    hand_options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_dir / "hand_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=2,
        min_hand_detection_confidence=0.35,
        min_hand_presence_confidence=0.35,
    )
    face_options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_dir / "face_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=2,
        min_face_detection_confidence=0.35,
        min_face_presence_confidence=0.35,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )
    return vision.HandLandmarker.create_from_options(hand_options), vision.FaceLandmarker.create_from_options(face_options)


def analyze(manifest_path: Path, asset_root: Path, model_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_assets = manifest.get("assets")
    if source_assets is None and "cases" in manifest:
        source_assets = [
            {
                "asset_id": item["case_id"],
                "type": "CASE_BASE",
                "path": item["path"],
                "interaction": item["interaction"],
            }
            for item in manifest["cases"]
        ]
    if not isinstance(source_assets, list):
        raise TypeError("manifest must contain assets or cases")
    model_hashes = {
        filename: sha256_file(model_dir / filename)
        for filename in ("hand_landmarker.task", "face_landmarker.task")
    }
    assets = []
    hand_detector, face_detector = create_detectors(model_dir)
    try:
        for asset in source_assets:
            needs_face = asset["type"] in FACE_ASSET_TYPES
            needs_hand = asset.get("interaction") == HAND_INTERACTION
            if not needs_face and not needs_hand:
                continue
            image = load_image(asset_root / asset["path"])
            result: dict = {"asset_id": asset["asset_id"]}
            if needs_face:
                face_result = face_detector.detect(image)
                faces = face_result.face_landmarks
                result["face"] = {"detected": bool(faces), "candidate_count": len(faces)}
                if faces:
                    selected_index = max(
                        range(len(faces)),
                        key=lambda index: normalized_box(faces[index])[2]
                        * normalized_box(faces[index])[3],
                    )
                    selected = faces[selected_index]
                    result["face"].update(
                        {
                            "landmark_count": len(selected),
                            "box_normalized": normalized_box(selected),
                            "mouth_corners_normalized": [point(selected[61]), point(selected[291])],
                            "lip_polygon_normalized": [point(selected[index]) for index in LIP_CONTOUR],
                            "mouth_mode": "FACE_LANDMARK",
                        }
                    )
                    matrices = face_result.facial_transformation_matrixes
                    if selected_index < len(matrices):
                        result["face"]["measured_pose_degrees"] = matrix_pose(
                            matrices[selected_index]
                        )
            if needs_hand:
                hand_result = hand_detector.detect(image)
                hands = hand_result.hand_landmarks
                result["hand"] = {"detected": bool(hands), "candidate_count": len(hands)}
                if hands:
                    candidates = []
                    for index, landmarks in enumerate(hands):
                        handedness = None
                        score = None
                        if index < len(hand_result.handedness) and hand_result.handedness[index]:
                            category = hand_result.handedness[index][0]
                            handedness = category.category_name
                            score = round(float(category.score), 6)
                        candidates.append(
                            {
                                "landmark_count": len(landmarks),
                                "box_normalized": normalized_box(landmarks),
                                "handedness": handedness,
                                "confidence": score,
                                "measured_grip_pose_degrees": hand_plane_pose(landmarks),
                                "landmarks_normalized": [point(item) for item in landmarks],
                            }
                        )
                    result["hand"]["candidates"] = candidates
            assets.append(result)
    finally:
        hand_detector.close()
        face_detector.close()

    return {
        "report_version": "1.0.0",
        "analyzer": "MediaPipe Tasks Vision 0.10.35",
        "manifest_sha256": sha256_file(manifest_path),
        "model_sha256": model_hashes,
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.manifest, args.asset_root, args.model_dir)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
