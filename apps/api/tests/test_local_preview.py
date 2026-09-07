import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from interaction_studio_api.config import Settings, get_settings
from interaction_studio_api.domain.local_preview import (
    PlacementParameters,
    PreviewProblem,
    PreviewRequest,
    bundle_bytes,
    catalog,
    mask_set,
    preserve_regions,
    render_preview,
)
from interaction_studio_api.main import app

PROJECT = Path(__file__).parents[3]


def array(data):
    with Image.open(io.BytesIO(data)) as image:
        return np.asarray(image).copy()


@pytest.fixture(scope="module")
def mouth_preview():
    return render_preview(PROJECT, PreviewRequest(case_id="DEV_MOUTH_001"))


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=PROJECT)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_settings, None)


def test_catalog_only_lists_sealed_development_inputs():
    result = catalog(PROJECT)
    assert len(result["cases"]) == 30
    assert len(result["product_views"]) == 11
    assert all(c["case_id"].startswith("DEV_") for c in result["cases"])
    assert {c["interaction"] for c in result["cases"]} == {"MOUTH", "NEAR_MOUTH", "HAND_HELD"}
    assert "path" not in json.dumps(result)
    assert result["provider_execution_performed"] is False


@pytest.mark.parametrize("case_id,anchor", [
    ("DEV_NEAR_001", "MOUTH_CORNER_OFFSET"),
    ("DEV_HAND_001", "HAND_THUMB_INDEX_MIDPOINT"),
])
def test_other_interactions_use_distinct_geometry(case_id, anchor):
    manifest, files = render_preview(PROJECT, PreviewRequest(case_id=case_id))
    assert manifest["anchor_method"] == anchor
    assert manifest["residual"]["within_gate"]
    assert not np.any(array(files["masks/M_occlusion.png"]))
    assert files["preview.png"].startswith(b"\x89PNG")


def test_preview_bundle_hashes_and_repeatability(mouth_preview):
    manifest, files = mouth_preview
    again, again_files = render_preview(PROJECT, PreviewRequest(case_id="DEV_MOUTH_001"))
    assert again == manifest and again_files == files
    assert bundle_bytes(files) == bundle_bytes(again_files)
    assert manifest["provider_execution_performed"] is False
    assert manifest["business_attempt_created"] is False
    assert manifest["formal_eligible"] is False
    with zipfile.ZipFile(io.BytesIO(bundle_bytes(files))) as archive:
        assert set(archive.namelist()) == set(files)
        for artifact in manifest["artifacts"]:
            data = archive.read(artifact["path"])
            assert hashlib.sha256(data).hexdigest() == artifact["sha256"]
    assert array(files["layers/depth.png"]).dtype == np.uint16
    assert len(manifest["sources"]["product_layer_sha256"]) == 5


def test_masks_partition_product_and_preserve_background(mouth_preview):
    _, files = mouth_preview
    masks = {name: array(files[f"masks/{name}.png"]) for name in
             ["M_product", "M_core", "M_transition", "M_contact", "M_occlusion",
              "M_visible_core"]}
    assert np.array_equal(masks["M_core"] | masks["M_transition"], masks["M_product"])
    assert not np.any(masks["M_core"] & masks["M_transition"])
    assert not np.any(masks["M_visible_core"] & masks["M_contact"])
    base = np.asarray(Image.open(PROJECT / "datasets/development/v1/cases/mouth/dev_mouth_001.png")
                      .convert("RGB"))
    preview = array(files["preview.png"])
    outside = masks["M_product"] == 0
    assert np.array_equal(preview[outside], base[outside])


def test_core_restore_rejects_unrelated_changes_and_keeps_occluder():
    alpha = np.zeros((100, 100), np.uint8)
    alpha[30:70, 30:70] = 255
    request = PreviewRequest(case_id="DEV_HAND_001", occlusion_polygons=[
        [(0.5, 0.2), (0.8, 0.2), (0.8, 0.8), (0.5, 0.8)]])
    masks = mask_set(alpha, request)
    base = np.full((100, 100, 3), 10, np.uint8)
    composite = base.copy()
    composite[alpha > 0] = 100
    edited = np.full_like(base, 200)
    result = preserve_regions(edited, composite, base, masks)
    assert np.all(result[masks["M_visible_core"] > 0] == 100)
    assert np.all(result[masks["M_contact"] > 0] == 200)
    assert np.all(result[masks["M_occlusion"] > 0] == 10)
    assert np.all(result[0, 0] == 10)
    assert not np.any(masks["M_contact"] & masks["M_occlusion"])
    with pytest.raises(ValueError, match="dimensions"):
        preserve_regions(edited[:10], composite, base, masks)


def test_manual_rotation_and_scale_are_bound_into_artifacts(mouth_preview):
    original, _ = mouth_preview
    params = PlacementParameters(**(original["request"]["placement"] | {"rotation_degrees": 30}))
    manifest, files = render_preview(PROJECT, PreviewRequest(case_id="DEV_MOUTH_001",
                                                             placement=params))
    assert manifest["preview_id"] != original["preview_id"]
    assert manifest["anchor_method"] == "MANUAL"
    product = array(files["masks/M_product.png"])
    rgba = array(files["layers/rgba.png"])
    assert np.array_equal(product > 0, rgba[:, :, 3] > 0)
    assert all(array(data).shape[:2] == product.shape for name, data in files.items()
               if name.endswith(".png"))


@pytest.mark.parametrize("change,code,status", [
    ({"case_id": "DEV_MOUTH_999"}, "DEVELOPMENT_CASE_NOT_FOUND", 404),
    ({"case_id": "DEV_MOUTH_011"}, "PRODUCT_RESIDUAL_EXCEEDED", 409),
    ({"product_view_id": "UNKNOWN"}, "PRODUCT_VIEW_NOT_FOUND", 404),
    ({"product_view_id": "LEFT30_UP15"}, "PRODUCT_RESIDUAL_EXCEEDED", 409),
    ({"placement": {"center_x": 0, "center_y": 0, "width_ratio": 0.2}},
     "PLACEMENT_CLIPS_PRODUCT", 409),
    ({"occlusion_polygons": [[(0, 0), (1, 0), (1, 1), (0, 1)]]},
     "VISIBLE_PRODUCT_CORE_EMPTY", 409),
])
def test_invalid_placements_fail_closed(client, change, code, status):
    response = client.post("/api/v1/development/previews?format=manifest",
                           json={"case_id": "DEV_MOUTH_001"} | change)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize("change", [
    {"case_id": "VAL_MOUTH_001"}, {"case_id": "../../seal.json"},
    {"dataset": "VALIDATION"}, {"provider": "openai"},
    {"placement": {"center_x": 1.1, "center_y": 0.5, "width_ratio": 0.2}},
    {"contact_radius_px": 1000},
    {"occlusion_polygons": [[(0.2, 0.2), (0.3, 0.3), (0.4, 0.4)]]},
])
def test_invalid_request_contract(client, change):
    response = client.post("/api/v1/development/previews",
                           json={"case_id": "DEV_MOUTH_001"} | change)
    assert response.status_code == 422


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_placement_rejected(value):
    with pytest.raises(ValueError):
        PlacementParameters(center_x=value, center_y=0.5, width_ratio=0.1)


@pytest.mark.parametrize("format,content_type", [
    ("png", "image/png"), ("bundle", "application/zip"), ("manifest", "application/json"),
])
def test_api_returns_downloadable_preview(client, format, content_type):
    response = client.post(f"/api/v1/development/previews?format={format}",
                           json={"case_id": "DEV_MOUTH_001"})
    assert response.status_code == 200
    assert response.headers["content-type"] == content_type
    assert len(response.headers["x-preview-id"]) == 64
    assert response.headers["cache-control"] == "no-store"


def test_missing_inputs_do_not_leak_server_paths(client, tmp_path):
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=tmp_path)
    for response in (client.get("/api/v1/development/catalog"),
                     client.post("/api/v1/development/previews",
                                 json={"case_id": "DEV_MOUTH_001"})):
        assert response.status_code == 503
        assert str(tmp_path) not in response.text


def test_modified_product_layer_rejected_without_mutating_real_assets(tmp_path):
    # Reference real read-only dataset sources; copy only product assets that are changed.
    for name in ("datasets", "workers"):
        shutil.copytree(PROJECT / name, tmp_path / name, symlinks=True,
                        ignore=shutil.ignore_patterns(".venv", "__pycache__"))
    shutil.copytree(PROJECT / "assets/production", tmp_path / "assets/production")
    path = tmp_path / "assets/production/product_master/v1/renders/front_00__rgba.png"
    path.write_bytes(b"corrupted")
    with pytest.raises(PreviewProblem, match="SOURCE_HASH_MISMATCH"):
        render_preview(tmp_path, PreviewRequest(case_id="DEV_MOUTH_001"))


def test_corrected_product_is_versioned_and_keeps_legacy_requests(mouth_preview):
    old, old_files = mouth_preview
    corrected, files = render_preview(
        PROJECT, PreviewRequest(case_id="DEV_MOUTH_001", product_revision="v2"))
    assert "product_revision" not in old["request"]
    assert corrected["request"]["product_revision"] == "v2"
    assert corrected["sources"]["dataset_manifest_sha256"] == old["sources"][
        "dataset_manifest_sha256"]
    assert corrected["sources"]["product_master_sha256"] != old["sources"][
        "product_master_sha256"]
    assert files["preview.png"] != old_files["preview.png"]
    assert corrected["contact_shadow"] == "GEOMETRIC_APPROXIMATION"
    assert render_preview(PROJECT, PreviewRequest(
        case_id="DEV_MOUTH_001", product_revision="v2")) == (corrected, files)
    base = np.asarray(Image.open(PROJECT / "datasets/development/v1/cases/mouth/dev_mouth_001.png")
                      .convert("RGB"))
    product = array(files["masks/M_product.png"])
    contact = array(files["masks/M_contact.png"])
    outside = (product == 0) & (contact == 0)
    assert np.array_equal(array(files["preview.png"])[outside], base[outside])
    assert np.any(array(files["masks/M_contact_shadow.png"]))
    assert not np.any(array(files["masks/M_contact_shadow.png"])[contact == 0])


def test_contact_shadow_preserves_foreground_and_never_applies_to_near_mouth():
    from interaction_studio_api.domain.local_preview import contact_shadow

    alpha = np.zeros((100, 100), np.float32)
    alpha[30:70, 30:70] = 1
    request = PreviewRequest(case_id="DEV_MOUTH_001", product_revision="v2",
                             placement=PlacementParameters(
                                 center_x=0.5, center_y=0.5, width_ratio=0.4),
                             occlusion_polygons=[[(0.5, 0), (1, 0), (1, 1), (0.5, 1)]])
    masks = mask_set((alpha * 255).astype(np.uint8), request)
    shadow = contact_shadow(alpha, masks, request)
    assert np.any(shadow[:, :50])
    assert not np.any(shadow[:, 50:])
    assert not np.any(shadow[masks["M_visible_core"] > 0])
    manifest, files = render_preview(PROJECT, PreviewRequest(
        case_id="DEV_NEAR_001", product_revision="v2"))
    assert manifest["contact_shadow"] == "NONE"
    assert "masks/M_contact_shadow.png" not in files


def test_corrected_product_endpoint_returns_selected_revision(client):
    path = "/api/v1/development/product-views/FRONT_00/image"
    old = client.get(path)
    corrected = client.get(path + "?product_revision=v2")
    assert corrected.status_code == 200
    assert old.content != corrected.content
    assert client.get(path + "?product_revision=v3").status_code == 422
