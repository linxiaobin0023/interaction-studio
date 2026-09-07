"""Model-free Development placement and mask preview. Never a production attempt."""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Annotated, Literal

import cv2
import numpy as np
from PIL import Image
from pydantic import Field, model_validator

from ..preflight.composite import choose_product, placement
from .dataset_releases import digest, local_path, read_release
from .resources import StrictContract

RECIPE_VERSION = "local-placement-v1"
V2_MASTER_SHA256 = "2c7e6db68f30eebda360dd0f925d154cce68f31ec7f13d39beb817ebdfd6db2d"
LAYERS = {"RGBA", "DEPTH", "NORMAL", "TRANSMISSION", "SPECULAR"}
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Point = tuple[Unit, Unit]
Polygon = Annotated[list[Point], Field(min_length=3, max_length=128)]


class PlacementParameters(StrictContract):
    center_x: Unit
    center_y: Unit
    # Width of the complete source layer canvas, not the silhouette bounding box.
    width_ratio: float = Field(ge=0.02, le=0.5, allow_inf_nan=False)
    rotation_degrees: float = Field(default=0, ge=-180, le=180, allow_inf_nan=False)


class PreviewRequest(StrictContract):
    case_id: str = Field(pattern=r"^DEV_(MOUTH|NEAR|HAND)_[0-9]{3}$")
    placement: PlacementParameters | None = None
    product_view_id: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,64}$")
    product_revision: Literal["v1", "v2"] = "v1"
    core_inset_px: int = Field(default=4, ge=1, le=32)
    contact_radius_px: int = Field(default=12, ge=1, le=64)
    occlusion_polygons: list[Polygon] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def no_degenerate_polygons(self) -> PreviewRequest:
        for polygon in self.occlusion_polygons:
            area = sum(a[0] * b[1] - b[0] * a[1]
                       for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True))
            if abs(area) < 1e-8:
                raise ValueError("occlusion polygon must enclose an area")
        return self


class PreviewProblem(ValueError):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


def checked_bytes(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise PreviewProblem("SOURCE_HASH_MISMATCH", 503)
    return data


def verified_inputs(root: Path, product_revision: str = "v1"
                    ) -> tuple[dict, dict, dict, list[dict]]:
    release = read_release(root, "development")
    if not release.seal_verified:
        raise PreviewProblem("DEVELOPMENT_RELEASE_NOT_READY", 503)
    dataset = root / "datasets/development/v1"
    # Recheck the exact bytes used, including landmark-to-manifest binding.
    seal = json.loads((dataset / "seal.json").read_text())
    bound = {local_path(root, ref["path"]): ref["sha256"] for ref in seal["evidence"]}
    manifest_path = dataset / "snapshot-manifest.json"
    snapshot = json.loads(checked_bytes(manifest_path, release.manifest_sha256))
    landmark_path = dataset / "evidence/landmarks.json"
    evidence = json.loads(checked_bytes(landmark_path, bound[landmark_path.resolve()]))
    if evidence["manifest_sha256"] != release.manifest_sha256:
        raise PreviewProblem("LANDMARK_BINDING_MISMATCH", 503)
    master_path = local_path(root, snapshot["product_master_manifest"])
    if product_revision == "v2":
        master_path = root / "assets/production/product_master/v2/render-manifest.json"
        master_bytes = checked_bytes(master_path, V2_MASTER_SHA256)
    elif product_revision == "v1":
        master_bytes = master_path.read_bytes()
    else:
        raise PreviewProblem("PRODUCT_REVISION_INVALID", 422)
    master = json.loads(master_bytes)
    views = []
    for view in master["views"]:
        outputs = view["outputs"]
        if len(outputs) != len(LAYERS) or {o["layer"] for o in outputs} != LAYERS:
            raise PreviewProblem("PRODUCT_LAYERS_INCOMPLETE", 503)
        if not all(math.isfinite(float(view[key])) for key in ("yaw", "pitch")):
            raise PreviewProblem("PRODUCT_POSE_INVALID", 503)
        views.append({**view, "view_yaw": view["yaw"], "view_pitch": view["pitch"],
                      "max_residual_yaw": 12, "max_residual_pitch": 8})
    if not views or len({v["view_id"] for v in views}) != len(views):
        raise PreviewProblem("PRODUCT_VIEWS_INVALID", 503)
    provenance = {
        "dataset_manifest_sha256": release.manifest_sha256,
        "landmarks_sha256": bound[landmark_path.resolve()],
        "product_master_sha256": hashlib.sha256(master_bytes).hexdigest(),
    }
    return snapshot, {e["asset_id"]: e for e in evidence["assets"]}, provenance, views


def recommendation(case: dict, landmark: dict, views: list[dict]) -> dict:
    x, y, width, method = placement(case, landmark)
    view, residual = choose_product(landmark, views)
    return {
        "placement": PlacementParameters(center_x=x, center_y=y, width_ratio=width).model_dump(),
        "anchor_method": method,
        "product_view_id": view["view_id"], "residual": residual,
    }


def catalog(root: Path) -> dict:
    snapshot, landmarks, provenance, views = verified_inputs(root, "v2")
    return {
        "dataset": "DEVELOPMENT", "version": snapshot["dataset_version"],
        "usage": "LOCAL_PREVIEW_ONLY", "provider_execution_performed": False,
        "provenance": provenance,
        "cases": [{key: case[key] for key in
                   ("case_id", "interaction", "pose_zone", "width", "height", "sha256")}
                  | {"suggestion": recommendation(case, landmarks[case["case_id"]], views)
                    | {"product_revision": "v2"}}
                  for case in snapshot["cases"]],
        "product_views": [{"view_id": v["view_id"], "yaw": v["yaw"], "pitch": v["pitch"]}
                          for v in views],
    }


def mask_set(alpha: np.ndarray, request: PreviewRequest) -> dict[str, np.ndarray]:
    product = (alpha > 0).astype(np.uint8) * 255
    inset = request.core_inset_px
    core = cv2.erode(product, np.ones((2 * inset + 1, 2 * inset + 1), np.uint8),
                     borderType=cv2.BORDER_CONSTANT, borderValue=0)
    radius = request.contact_radius_px
    outer = cv2.dilate(product, np.ones((2 * radius + 1, 2 * radius + 1), np.uint8))
    occlusion = np.zeros_like(product)
    h, w = product.shape
    for polygon in request.occlusion_polygons:
        points = np.rint(np.array(polygon) * [w - 1, h - 1]).astype(np.int32)
        cv2.fillPoly(occlusion, [points], 255)
    occlusion = cv2.bitwise_and(occlusion, product)
    visible_core = cv2.bitwise_and(core, cv2.bitwise_not(occlusion))
    contact = cv2.bitwise_and(outer, cv2.bitwise_not(core))
    # Foreground occluders must also stay unchanged by a future edit.
    contact = cv2.bitwise_and(contact, cv2.bitwise_not(occlusion))
    return {"M_product": product, "M_core": core,
            "M_transition": cv2.subtract(product, core), "M_contact": contact,
            "M_occlusion": occlusion, "M_visible_core": visible_core}


def preserve_regions(edited: np.ndarray, pre_composite: np.ndarray,
                     base: np.ndarray, masks: dict[str, np.ndarray]) -> np.ndarray:
    """Restore visible core and all pixels outside the editable contact band."""
    if edited.shape != base.shape or pre_composite.shape != base.shape:
        raise ValueError("image dimensions must match")
    if any(mask.shape != base.shape[:2] for mask in masks.values()):
        raise ValueError("mask dimensions must match")
    result = edited.copy()
    result[masks["M_contact"] == 0] = pre_composite[masks["M_contact"] == 0]
    visible = masks["M_visible_core"] > 0
    result[visible] = pre_composite[visible]
    occluded = masks["M_occlusion"] > 0
    result[occluded] = base[occluded]
    return result


def contact_shadow(alpha: np.ndarray, masks: dict[str, np.ndarray],
                   request: PreviewRequest) -> np.ndarray:
    """Small geometric contact cue; never a learned lighting/occlusion estimate."""
    h, w = alpha.shape
    sigma = max(0.6, min(3.0, w * request.placement.width_ratio * 0.015))
    shadow = cv2.GaussianBlur(alpha, (0, 0), sigmaX=sigma, sigmaY=sigma) * 0.22
    shadow *= 1 - alpha
    shadow[masks["M_contact"] == 0] = 0
    # Preserve the whole user-drawn foreground polygon, including the contact band.
    protected = np.zeros((h, w), np.uint8)
    for polygon in request.occlusion_polygons:
        points = np.rint(np.array(polygon) * [w - 1, h - 1]).astype(np.int32)
        cv2.fillPoly(protected, [points], 255)
    shadow[protected > 0] = 0
    return shadow


def png_bytes(array: np.ndarray) -> bytes:
    out = io.BytesIO()
    Image.fromarray(array).save(out, format="PNG")
    return out.getvalue()


def render_preview(root: Path, request: PreviewRequest) -> tuple[dict, dict[str, bytes]]:
    snapshot, landmarks, provenance, views = verified_inputs(root, request.product_revision)
    case = next((c for c in snapshot["cases"] if c["case_id"] == request.case_id), None)
    if case is None:
        raise PreviewProblem("DEVELOPMENT_CASE_NOT_FOUND", 404)
    landmark = landmarks[case["case_id"]]
    suggested = recommendation(case, landmark, views)
    view_id = request.product_view_id or suggested["product_view_id"]
    view = next((v for v in views if v["view_id"] == view_id), None)
    if view is None:
        raise PreviewProblem("PRODUCT_VIEW_NOT_FOUND", 404)
    _, residual = choose_product(landmark, [view])
    if not residual["within_gate"]:
        raise PreviewProblem("PRODUCT_RESIDUAL_EXCEEDED")
    params = request.placement or PlacementParameters(**suggested["placement"])
    dataset = root / "datasets/development/v1"
    base_data = checked_bytes(local_path(dataset, case["path"]), case["sha256"])
    with Image.open(io.BytesIO(base_data)) as image:
        base = np.asarray(image.convert("RGB"))
    h, w = base.shape[:2]
    if [w, h] != [case["width"], case["height"]] or max(w, h) > 4096:
        raise PreviewProblem("CASE_DIMENSIONS_INVALID", 503)
    layers = {}
    layer_hashes = {}
    for output in view["outputs"]:
        data = checked_bytes(local_path(root, output["path"]), output["sha256"])
        with Image.open(io.BytesIO(data)) as image:
            layers[output["layer"]] = np.asarray(image).copy()
        layer_hashes[output["layer"]] = output["sha256"]
    rgba = layers["RGBA"]
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise PreviewProblem("PRODUCT_RGBA_INVALID", 503)
    sh, sw = rgba.shape[:2]
    expected_shapes = {"RGBA": (sh, sw, 4), "NORMAL": (sh, sw, 3),
                       "DEPTH": (sh, sw), "TRANSMISSION": (sh, sw), "SPECULAR": (sh, sw)}
    if any(layers[name].shape != shape for name, shape in expected_shapes.items()):
        raise PreviewProblem("PRODUCT_LAYER_DIMENSIONS_INVALID", 503)
    matrix = cv2.getRotationMatrix2D(((sw - 1) / 2, (sh - 1) / 2),
                                    params.rotation_degrees, w * params.width_ratio / sw)
    matrix[:, 2] += [params.center_x * (w - 1) - (sw - 1) / 2,
                     params.center_y * (h - 1) - (sh - 1) / 2]
    ys, xs = np.nonzero(rgba[:, :, 3])
    if not len(xs):
        raise PreviewProblem("PRODUCT_ALPHA_EMPTY", 503)
    corners = np.array([[xs.min(), ys.min(), 1], [xs.max(), ys.min(), 1],
                        [xs.max(), ys.max(), 1], [xs.min(), ys.max(), 1]]) @ matrix.T
    if np.any(corners < 1) or np.any(corners > [w - 2, h - 2]):
        raise PreviewProblem("PLACEMENT_CLIPS_PRODUCT")

    def warp(array: np.ndarray, interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
        return cv2.warpAffine(array, matrix, (w, h), flags=interpolation,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # Premultiply before sampling, so transparent black edges do not darken the product.
    alpha_source = rgba[:, :, 3].astype(np.float32) / 255
    alpha = warp(alpha_source)
    rgb_premultiplied = warp(rgba[:, :, :3].astype(np.float32) * alpha_source[:, :, None])
    transformed = np.zeros((h, w, 4), dtype=np.uint8)
    transformed[:, :, :3] = np.rint(np.clip(
        rgb_premultiplied / np.maximum(alpha[:, :, None], 1e-8), 0, 255)).astype(np.uint8)
    transformed[:, :, 3] = np.rint(alpha * 255).astype(np.uint8)
    composite = np.rint(np.clip(rgb_premultiplied + base * (1 - alpha[:, :, None]),
                                0, 255)).astype(np.uint8)
    masks = mask_set(transformed[:, :, 3], request)
    if not np.any(masks["M_visible_core"]):
        raise PreviewProblem("VISIBLE_PRODUCT_CORE_EMPTY")
    edited = composite
    shadow = None
    if request.product_revision == "v2" and case["interaction"] == "MOUTH":
        shadow = contact_shadow(alpha, masks, request.model_copy(update={"placement": params}))
        edited = np.rint(composite.astype(np.float32) * (1 - shadow[:, :, None])).astype(np.uint8)
    preview = preserve_regions(edited, composite, base, masks)
    files = {"preview.png": png_bytes(preview), "layers/rgba.png": png_bytes(transformed)}
    if shadow is not None:
        files["masks/M_contact_shadow.png"] = png_bytes(np.rint(shadow * 255).astype(np.uint8))
    for name in LAYERS - {"RGBA"}:
        # Normal channels remain in the source frame; these are diagnostic layers,
        # not re-lit/refracted material synthesis. Depth retains 16-bit precision.
        files[f"layers/{name.lower()}.png"] = png_bytes(warp(layers[name], cv2.INTER_NEAREST))
    for name, mask in masks.items():
        files[f"masks/{name}.png"] = png_bytes(mask)
    normalized = request.model_dump() | {"placement": params.model_dump(),
                                         "product_view_id": view_id}
    if request.product_revision == "v1":
        normalized.pop("product_revision", None)
    identity = {"recipe_version": ("local-placement-v2" if request.product_revision == "v2"
                                   else RECIPE_VERSION), "request": normalized,
                "sources": provenance | {"case_base_sha256": case["sha256"],
                                           "product_layer_sha256": layer_hashes},
                "implementation_sha256": digest(Path(__file__)),
                "geometry_sha256": digest(Path(__file__).parents[1] / "preflight/composite.py"),
                "runtime": {"opencv": cv2.__version__, "numpy": np.__version__,
                            "pillow": Image.__version__}}
    preview_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    manifest = identity | {
        "preview_id": preview_id, "status": "LOCAL_PREVIEW_ONLY", "dataset": "DEVELOPMENT",
        "interaction": case["interaction"], "provider_execution_performed": False,
        "formal_eligible": False, "business_attempt_created": False,
        "width": w, "height": h, "residual": residual,
        "anchor_method": "MANUAL" if request.placement else suggested["anchor_method"],
        "affine_source_to_base": matrix.tolist(),
        "mask_semantics": "255=included; 0=excluded; M_contact is the editable band",
        "limitations": ["CONTACT_GEOMETRY_NOT_REPAIRED", "MATERIAL_RELIGHTING_NOT_APPLIED",
                        "NORMAL_CHANNELS_RETAIN_SOURCE_FRAME",
                        "MASK_PARAMETERS_NOT_BENCHMARK_FROZEN",
                        "MANUAL_OCCLUSION_ONLY", "PLACEMENT_ACCURACY_NOT_VALIDATED",
                        "CONTACT_BAND_IS_GEOMETRIC_NOT_ANATOMICAL",
                        "PROXIMITY_GATE_NOT_VALIDATED"],
        "artifacts": [{"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                       "bytes": len(data)} for name, data in sorted(files.items())],
    }
    if request.product_revision == "v2":
        manifest["contact_shadow"] = "GEOMETRIC_APPROXIMATION" if shadow is not None else "NONE"
    files["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    return manifest, files


def bundle_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output.getvalue()


PreviewFormat = Literal["bundle", "png", "manifest"]
