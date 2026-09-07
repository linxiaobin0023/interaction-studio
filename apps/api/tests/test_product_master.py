import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_product_master_outputs_are_hash_bound_and_complete() -> None:
    project_root = Path(__file__).parents[3]
    manifest_path = (
        project_root / "assets/production/product_master/v1/render-manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())

    assert manifest["deterministic"] is True
    assert manifest["product_sku"] == "SKU_PROD_PACIFIER_001"
    assert len(manifest["views"]) == 11
    assert len({(item["yaw"], item["pitch"]) for item in manifest["views"]}) == 11
    for view in manifest["views"]:
        assert view["pose_source"] == "PARAMETRIC_CAMERA_GROUND_TRUTH"
        assert {item["layer"] for item in view["outputs"]} == {
            "RGBA",
            "DEPTH",
            "NORMAL",
            "TRANSMISSION",
            "SPECULAR",
        }
        for output in view["outputs"]:
            path = project_root / output["path"]
            assert path.is_file()
            assert sha256_file(path) == output["sha256"]


def test_front_product_has_real_alpha_and_material_layers() -> None:
    project_root = Path(__file__).parents[3]
    render_root = project_root / "assets/production/product_master/v1/renders"
    rgba = Image.open(render_root / "front_00__rgba.png")
    alpha = rgba.getchannel("A")
    transmission = Image.open(render_root / "front_00__transmission.png")

    assert rgba.mode == "RGBA"
    assert alpha.getextrema() == (0, 255)
    assert any(0 < value < 255 for value in alpha.getdata())
    assert transmission.getextrema()[1] > transmission.getextrema()[0]


def test_corrected_nipple_points_behind_shield_and_is_hidden_in_front():
    import numpy as np

    root = Path(__file__).parents[3]
    spec = json.loads((root / "workers/product_master/product-master-v2.json").read_text())
    nipple = spec["geometry"]["nipple"]
    assert nipple["center"][2] < 0
    assert nipple["half_extents"][2] > nipple["half_extents"][1]
    assert nipple["center"][1] == spec["geometry"]["button"]["center"][1]
    renders = root / "assets/production/product_master/v2/renders"
    front = np.asarray(Image.open(renders / "front_00__transmission.png"))
    side = np.asarray(Image.open(renders / "right90_00__transmission.png"))
    assert front.max() < 100  # No clear nipple protrudes above the front shield.
    assert side.max() > 150  # The nipple still exists behind the shield in side view.
    manifest = json.loads((renders.parent / "render-manifest.json").read_text())
    assert sha256_file(root / manifest["spec_path"]) == manifest["spec_sha256"]
    for view in manifest["views"]:
        for layer in view["outputs"]:
            assert sha256_file(root / layer["path"]) == layer["sha256"]
