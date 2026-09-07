import json
from pathlib import Path

from interaction_studio_api.preflight.spike import sha256_file


def test_composite_report_is_bound_to_manifest_and_outputs() -> None:
    project_root = Path(__file__).parents[3]
    report_path = project_root / "docs/preflight/mock-v0-composites.json"
    report = json.loads(report_path.read_text())
    manifest = project_root / "mock_assets/v0/metadata/asset_manifest.json"

    assert report["manifest_sha256"] == sha256_file(manifest)
    assert report["composite_count"] == 10
    assert all(item["residual"]["within_gate"] for item in report["outputs"])
    for item in report["outputs"]:
        output = project_root / item["output_path"]
        assert output.is_file()
        assert sha256_file(output) == item["output_sha256"]


def test_material_decision_keeps_required_layers() -> None:
    project_root = Path(__file__).parents[3]
    report = json.loads(
        (project_root / "docs/preflight/mock-v0-composites.json").read_text()
    )

    decision = report["material_decision"]
    assert decision["transmission_specular_required"] is True
    assert decision["interior_partial_alpha_ratio"] < decision["decision_threshold"]
