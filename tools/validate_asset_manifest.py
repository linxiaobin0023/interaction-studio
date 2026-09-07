"""Verify local asset paths, SHA256 values and PNG dimensions in an asset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as file_handle:
        header = file_handle.read(24)
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def safe_asset_path(root: Path, relative: str) -> Path | None:
    pure_path = PurePosixPath(relative)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    candidate = (root / Path(*pure_path.parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def validate_manifest(manifest_path: Path, root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"cannot read manifest: {exc}"], "warnings": []}

    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        return {"valid": False, "errors": ["assets must be a non-empty array"], "warnings": []}

    asset_ids = [asset.get("asset_id") for asset in assets if isinstance(asset, dict)]
    paths = [asset.get("path") for asset in assets if isinstance(asset, dict)]
    for value, count in Counter(asset_ids).items():
        if value is None or count > 1:
            errors.append(f"duplicate or missing asset_id: {value!r}")
    for value, count in Counter(paths).items():
        if value is None or count > 1:
            errors.append(f"duplicate or missing asset path: {value!r}")

    if manifest.get("provenance") == "SYNTHETIC_MOCK" and manifest.get("formal_eligible"):
        errors.append("SYNTHETIC_MOCK manifest cannot be Formal-eligible")

    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            errors.append(f"asset[{index}] must be an object")
            continue
        asset_id = asset.get("asset_id", f"asset[{index}]")
        relative_path = asset.get("path")
        if not isinstance(relative_path, str):
            errors.append(f"{asset_id}: path must be a string")
            continue
        asset_path = safe_asset_path(root, relative_path)
        if asset_path is None:
            errors.append(f"{asset_id}: unsafe path {relative_path!r}")
            continue
        if not asset_path.is_file():
            errors.append(f"{asset_id}: file not found: {relative_path}")
            continue

        expected_hash = asset.get("sha256")
        actual_hash = sha256_file(asset_path)
        if expected_hash != actual_hash:
            errors.append(f"{asset_id}: SHA256 mismatch")

        dimensions = png_dimensions(asset_path)
        if dimensions is None:
            warnings.append(f"{asset_id}: dimension validation supports PNG only")
            continue
        expected_dimensions = (asset.get("width"), asset.get("height"))
        if dimensions != expected_dimensions:
            errors.append(
                f"{asset_id}: dimensions {dimensions} do not match {expected_dimensions}"
            )

    counts = Counter(
        asset.get("type", "UNKNOWN") for asset in assets if isinstance(asset, dict)
    )
    if manifest.get("readiness_status") == "PILOT_ONLY":
        warnings.append("manifest is PILOT_ONLY and cannot satisfy a readiness gate")

    return {
        "valid": not errors,
        "manifest": str(manifest_path),
        "root": str(root),
        "asset_count": len(assets),
        "counts_by_type": dict(sorted(counts.items())),
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        help="asset root; defaults to the manifest directory's parent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    root = args.root.resolve() if args.root else manifest_path.parent.parent
    result = validate_manifest(manifest_path, root)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
