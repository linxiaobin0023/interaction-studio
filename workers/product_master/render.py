"""Deterministic CPU SDF renderer for the authoritative fictional pacifier master."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

MAX_STEPS = 112
MAX_DISTANCE = 8.0
HIT_EPSILON = 0.0018


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ellipsoid(points: np.ndarray, radii: tuple[float, float, float]) -> np.ndarray:
    radius = np.asarray(radii, dtype=np.float32)
    k0 = np.linalg.norm(points / radius, axis=-1)
    k1 = np.linalg.norm(points / (radius * radius), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def cylinder_z(
    points: np.ndarray, center_x: float, center_y: float, radius: float, half_depth: float
) -> np.ndarray:
    radial = np.linalg.norm(
        points[..., :2] - np.asarray([center_x, center_y], dtype=np.float32), axis=-1
    ) - radius
    axial = np.abs(points[..., 2]) - half_depth
    outside = np.linalg.norm(np.maximum(np.stack([radial, axial], axis=-1), 0), axis=-1)
    return outside + np.minimum(np.maximum(radial, axial), 0)


def torus_z(
    points: np.ndarray, center_y: float, center_z: float, major: float, minor: float
) -> np.ndarray:
    radial = np.linalg.norm(
        np.stack([points[..., 0], points[..., 1] - center_y], axis=-1), axis=-1
    ) - major
    return np.linalg.norm(
        np.stack([radial, points[..., 2] - center_z], axis=-1), axis=-1
    ) - minor


def scene(points: np.ndarray, model: dict) -> tuple[np.ndarray, np.ndarray]:
    geometry = model["geometry"]
    shield_spec = geometry["shield"]
    lobes = []
    for center_x in shield_spec["lobe_centers_x"]:
        center = np.asarray(
            [center_x, shield_spec["lobe_center_y"], 0], dtype=np.float32
        )
        lobes.append(
            ellipsoid(points - center, tuple(shield_spec["lobe_half_extents"]))
        )
    waist = ellipsoid(
        points - np.asarray(shield_spec["waist_center"], dtype=np.float32),
        tuple(shield_spec["waist_half_extents"]),
    )
    shield = np.minimum(np.minimum(lobes[0], lobes[1]), waist)
    for center_x, center_y in shield_spec["ventilation_hole_centers"]:
        hole = cylinder_z(
            points,
            center_x,
            center_y,
            shield_spec["ventilation_hole_radius"],
            0.32,
        )
        shield = np.maximum(shield, -hole)

    button_spec = geometry["button"]
    button_points = points - np.asarray(button_spec["center"], dtype=np.float32)
    button = cylinder_z(
        button_points, 0, 0, button_spec["radius"], button_spec["half_depth"]
    )
    ring_spec = geometry["ring"]
    ring = torus_z(
        points,
        ring_spec["center"][1],
        ring_spec["center"][2],
        ring_spec["major_radius"],
        ring_spec["minor_radius"],
    )
    nipple_spec = geometry["nipple"]
    nipple_points = points - np.asarray(nipple_spec["center"], dtype=np.float32)
    nipple = ellipsoid(nipple_points, tuple(nipple_spec["half_extents"]))

    body = np.minimum(np.minimum(shield, button), ring)
    distance = np.minimum(body, nipple)
    material = np.where(nipple < body, 2, 1).astype(np.uint8)
    return distance, material


def rotation_matrix(yaw: float, pitch: float) -> np.ndarray:
    y = math.radians(yaw)
    x = math.radians(pitch)
    rotate_y = np.asarray(
        [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]],
        dtype=np.float32,
    )
    rotate_x = np.asarray(
        [[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]],
        dtype=np.float32,
    )
    return rotate_x @ rotate_y


def sdf_world(
    points: np.ndarray, inverse_rotation: np.ndarray, model: dict
) -> tuple[np.ndarray, np.ndarray]:
    return scene(points @ inverse_rotation.T, model)


def normals(points: np.ndarray, inverse_rotation: np.ndarray, model: dict) -> np.ndarray:
    epsilon = 0.0025
    gradients = []
    for axis in range(3):
        offset = np.zeros(3, dtype=np.float32)
        offset[axis] = epsilon
        positive, _ = sdf_world(points + offset, inverse_rotation, model)
        negative, _ = sdf_world(points - offset, inverse_rotation, model)
        gradients.append((positive - negative) / (2 * epsilon))
    normal = np.stack(gradients, axis=-1)
    return normal / np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-6)


def render_view(
    yaw: float,
    pitch: float,
    size: int,
    fov_degrees: float,
    camera_distance: float,
    model: dict,
) -> dict[str, np.ndarray]:
    coordinates = (np.arange(size, dtype=np.float32) + 0.5) / size * 2 - 1
    grid_x, grid_y = np.meshgrid(coordinates, -coordinates)
    scale = math.tan(math.radians(fov_degrees) / 2)
    directions = np.stack(
        [grid_x * scale, grid_y * scale, -np.ones_like(grid_x)], axis=-1
    )
    directions /= np.linalg.norm(directions, axis=-1, keepdims=True)
    origin = np.zeros_like(directions)
    origin[..., 2] = camera_distance
    travel = np.zeros((size, size), dtype=np.float32)
    hit = np.zeros((size, size), dtype=bool)
    active = np.ones((size, size), dtype=bool)
    inverse_rotation = rotation_matrix(yaw, pitch).T
    material = np.zeros((size, size), dtype=np.uint8)

    for _ in range(MAX_STEPS):
        points = origin + directions * travel[..., None]
        distance, current_material = sdf_world(points, inverse_rotation, model)
        newly_hit = active & (distance < HIT_EPSILON)
        material[newly_hit] = current_material[newly_hit]
        hit |= newly_hit
        active &= ~newly_hit
        travel[active] += np.maximum(distance[active], HIT_EPSILON * 0.35)
        active &= travel < MAX_DISTANCE
        if not np.any(active):
            break

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    normal_image = np.zeros((size, size, 3), dtype=np.uint8)
    transmission = np.zeros((size, size), dtype=np.uint8)
    specular = np.zeros((size, size), dtype=np.uint8)
    depth = np.zeros((size, size), dtype=np.uint16)
    if np.any(hit):
        points = origin[hit] + directions[hit] * travel[hit, None]
        normal = normals(points, inverse_rotation, model)
        light = np.asarray([-0.42, 0.68, 0.61], dtype=np.float32)
        light /= np.linalg.norm(light)
        view = -directions[hit]
        half_vector = light + view
        half_vector /= np.maximum(np.linalg.norm(half_vector, axis=-1, keepdims=True), 1e-6)
        diffuse = np.clip(normal @ light, 0, 1)
        shine = np.power(np.clip(np.sum(normal * half_vector, axis=-1), 0, 1), 28)
        materials = model["materials"]
        body_color = np.asarray(materials["sage_body"]["base_color_srgb"], dtype=np.float32)
        nipple_color = np.asarray(
            materials["clear_nipple"]["base_color_srgb"], dtype=np.float32
        )
        base_color = np.where((material[hit] == 2)[:, None], nipple_color, body_color)
        shaded = base_color * (0.48 + 0.52 * diffuse[:, None]) + 92 * shine[:, None]
        rgba[hit, :3] = np.clip(shaded, 0, 255).astype(np.uint8)
        nipple_alpha = round(
            (1 - materials["clear_nipple"]["transmission"] * 0.68) * 255
        )
        rgba[hit, 3] = np.where(material[hit] == 2, nipple_alpha, 255).astype(
            np.uint8
        )
        normal_image[hit] = np.clip((normal * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
        transmission[hit] = np.where(
            material[hit] == 2,
            round(materials["clear_nipple"]["transmission"] * 255),
            round(materials["sage_body"]["transmission"] * 255),
        ).astype(np.uint8)
        specular[hit] = np.clip(
            shine
            * np.where(
                material[hit] == 2,
                materials["clear_nipple"]["specular"] * 255,
                materials["sage_body"]["specular"] * 255,
            ),
            0,
            255,
        ).astype(np.uint8)
        normalized_depth = np.clip((camera_distance - travel[hit]) / 2.5, 0, 1)
        depth[hit] = (normalized_depth * 65535).astype(np.uint16)
    return {
        "rgba": rgba,
        "depth": depth,
        "normal": normal_image,
        "transmission": transmission,
        "specular": specular,
    }


def save_outputs(output_dir: Path, view_id: str, outputs: dict[str, np.ndarray]) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for layer, array in outputs.items():
        path = output_dir / f"{view_id.lower()}__{layer}.png"
        if layer == "rgba":
            image = Image.fromarray(array, "RGBA")
        elif layer == "normal":
            image = Image.fromarray(array, "RGB")
        elif layer == "depth":
            image = Image.fromarray(array, "I;16")
        else:
            image = Image.fromarray(array, "L")
        image.save(path, format="PNG", optimize=True)
        records.append(
            {
                "layer": layer.upper(),
                "path": str(path),
                "sha256": sha256_file(path),
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    camera = spec["camera"]
    view_records = []
    for view in spec["views"]:
        outputs = render_view(
            float(view["yaw"]),
            float(view["pitch"]),
            args.size,
            float(camera["vertical_fov_degrees"]),
            float(camera["distance"]),
            spec,
        )
        view_records.append(
            {
                **view,
                "pose_source": "PARAMETRIC_CAMERA_GROUND_TRUTH",
                "outputs": save_outputs(args.output_dir, view["view_id"], outputs),
            }
        )
    manifest = {
        "manifest_version": "1.0.0",
        "product_sku": spec["product_sku"],
        "master_version": spec["master_version"],
        "spec_path": str(args.spec),
        "spec_sha256": sha256_file(args.spec),
        "renderer_sha256": sha256_file(Path(__file__)),
        "deterministic": True,
        "views": view_records,
    }
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
