import json
from pathlib import Path

from interaction_studio_api.domain.manifests import AssetManifest
from interaction_studio_api.preflight.spike import run_structural_preflight, sha256_file


def load_mock_pack() -> tuple[AssetManifest, Path]:
    project_root = Path(__file__).parents[3]
    root = project_root / "mock_assets/v0"
    manifest = AssetManifest.model_validate_json(
        (root / "metadata/asset_manifest.json").read_text()
    )
    return manifest, root


def load_evidence() -> tuple[dict, dict, dict]:
    project_root = Path(__file__).parents[3]
    landmarks = json.loads(
        (project_root / "docs/preflight/mock-v0-landmarks.json").read_text()
    )
    composites = json.loads(
        (project_root / "docs/preflight/mock-v0-composites.json").read_text()
    )
    anatomy = json.loads(
        (project_root / "docs/preflight/mock-v0-hand-anatomy-review.json").read_text()
    )
    return landmarks, composites, anatomy


def test_structural_spike_records_raw_measurements() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )

    assert report["technical_status"] == "CONDITIONAL"
    assert report["gate_effect"] == "NONE"
    assert len(report["raw_measurements"]["faces"]) == 13
    assert all(item["detected"] for item in report["raw_measurements"]["faces"])
    assert report["blocking_conditions"] == []
    assert len(report["raw_measurements"]["pairwise_residuals"]) == 10
    assert all(
        item["within_gate"] for item in report["raw_measurements"]["pairwise_residuals"]
    )


def test_missing_model_evidence_remains_blocked() -> None:
    manifest, root = load_mock_pack()

    report = run_structural_preflight(manifest, root)

    assert report["technical_status"] == "BLOCKED"
    assert "MOUTH_GEOMETRY" in report["blocking_conditions"]
    assert "PRODUCT_RESIDUAL_METADATA" in report["blocking_conditions"]
    assert "MATERIAL_LAYERING_DECISION" in report["blocking_conditions"]
    assert "HAND_LANDMARK" in report["blocking_conditions"]
    assert "HAND_ANATOMY_QC" in report["blocking_conditions"]


def test_anatomy_report_must_cover_exact_hand_case_set() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()
    anatomy["assets"].pop()

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )

    assert "HAND_ANATOMY_QC" in report["blocking_conditions"]


def test_forged_model_hash_is_not_trusted() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()
    landmarks["model_sha256"]["hand_landmarker.task"] = "0" * 64

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )

    assert "MOUTH_GEOMETRY" in report["blocking_conditions"]
    assert "HAND_LANDMARK" in report["blocking_conditions"]


def test_incomplete_composite_report_is_not_trusted() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()
    composites["outputs"].pop()
    composites["composite_count"] -= 1

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )

    assert "MATERIAL_LAYERING_DECISION" in report["blocking_conditions"]


def test_composite_hash_mismatch_is_not_trusted() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()
    composites["outputs"][0]["output_sha256"] = "0" * 64

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )

    assert "MATERIAL_LAYERING_DECISION" in report["blocking_conditions"]


def test_material_background_measurement_uses_pixels() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()

    report = run_structural_preflight(
        manifest,
        root,
        landmark_report=landmarks,
        composite_report=composites,
        anatomy_report=anatomy,
        manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
    )
    material = next(
        item for item in report["checks"] if item["check_id"] == "MATERIAL_BACKGROUND_MEASUREMENT"
    )
    luma = material["observed"]["corner_luma"]

    assert material["status"] == "PASS"
    assert luma["WHITE"] > luma["GRAY"] > luma["BLACK"]


def test_preflight_report_is_json_serializable() -> None:
    manifest, root = load_mock_pack()
    landmarks, composites, anatomy = load_evidence()

    encoded = json.dumps(
        run_structural_preflight(
            manifest,
            root,
            landmark_report=landmarks,
            composite_report=composites,
            anatomy_report=anatomy,
            manifest_sha256=sha256_file(root / "metadata/asset_manifest.json"),
        )
    )

    assert "synthetic-mock-v0.2" in encoded
