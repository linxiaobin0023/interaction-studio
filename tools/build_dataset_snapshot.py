"""Build a hash-bound snapshot manifest from a dataset case index."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath

from PIL import Image


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe dataset path: {relative}")
    path = (root / Path(*pure.parts)).resolve()
    path.relative_to(root.resolve())
    return path


def build_snapshot(index_path: Path, dataset_root: Path) -> dict:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    cases = []
    for item in index["cases"]:
        path = safe_path(dataset_root, item["path"])
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
        cases.append(
            {
                **item,
                "sha256": sha256_file(path),
                "width": width,
                "height": height,
                "mode": mode,
            }
        )

    ids = [item["case_id"] for item in cases]
    paths = [item["path"] for item in cases]
    hashes = [item["sha256"] for item in cases]
    jobs = [item["generation_job_id"] for item in cases]
    for name, values in {
        "case_id": ids,
        "path": paths,
        "sha256": hashes,
        "generation_job_id": jobs,
    }.items():
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {name} in dataset snapshot")

    target = int(index["target_case_count"])
    if target <= 0 or len(cases) > target:
        raise ValueError("case count must not exceed a positive target")
    return {
        "manifest_version": "1.0.0",
        "dataset": index["dataset"],
        "dataset_version": index["dataset_version"],
        "provenance": "PROJECT_OWNED_SYNTHETIC",
        # A complete inventory still needs pose, anatomy and independence admission.
        "readiness_status": "CANDIDATE_COMPLETE" if len(cases) == target else "IN_PROGRESS",
        "formal_eligible": False,
        "target_case_count": target,
        "actual_case_count": len(cases),
        "remaining_case_count": target - len(cases),
        "interaction_counts": dict(sorted(Counter(item["interaction"] for item in cases).items())),
        "pose_counts": dict(sorted(Counter(item["pose_zone"] for item in cases).items())),
        "character_id": index["character_id"],
        "character_canonical_sha256": index["character_canonical_sha256"],
        "product_sku": index["product_sku"],
        "product_master_manifest": index["product_master_manifest"],
        "index_sha256": sha256_file(index_path),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = build_snapshot(args.index, args.dataset_root)
    encoded = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if (args.dataset_root / "seal.json").exists() and (
        not args.output.exists() or args.output.read_text(encoding="utf-8") != encoded
    ):
        raise ValueError("sealed dataset cannot be rebuilt with changed inputs; use a new version")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        encoded, encoding="utf-8"
    )
    checksum = args.output.with_suffix(args.output.suffix + ".sha256")
    checksum.write_text(f"{sha256_file(args.output)}  {args.output.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": snapshot["readiness_status"],
                "actual": snapshot["actual_case_count"],
                "target": snapshot["target_case_count"],
                "remaining": snapshot["remaining_case_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
