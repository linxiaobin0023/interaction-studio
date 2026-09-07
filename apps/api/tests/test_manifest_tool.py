import importlib.util
from pathlib import Path

TOOL_PATH = Path(__file__).parents[3] / "tools" / "validate_asset_manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_asset_manifest", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_repository_mock_manifest_is_valid() -> None:
    project_root = Path(__file__).parents[3]
    manifest = project_root / "mock_assets/v0/metadata/asset_manifest.json"

    result = MODULE.validate_manifest(manifest, manifest.parent.parent)

    assert result["valid"] is True
    assert result["asset_count"] == 27
    assert result["errors"] == []
    assert "PILOT_ONLY" in result["warnings"][0]


def test_safe_asset_path_rejects_traversal(tmp_path: Path) -> None:
    assert MODULE.safe_asset_path(tmp_path, "../outside.png") is None
