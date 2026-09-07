"""Run the local, non-inference G1 structural preflight spike."""

import argparse
import json
import sys
from pathlib import Path

from interaction_studio_api.domain.manifests import AssetManifest
from interaction_studio_api.preflight.spike import run_structural_preflight, sha256_file
from pydantic import ValidationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--hand-not-core", action="store_true")
    parser.add_argument("--exclude-side-views", action="store_true")
    parser.add_argument("--landmarks", type=Path)
    parser.add_argument("--composites", type=Path)
    parser.add_argument("--anatomy", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = AssetManifest.model_validate_json(args.manifest.read_text())
    except (OSError, ValidationError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    manifest_hash = sha256_file(args.manifest)
    landmark_report = json.loads(args.landmarks.read_text()) if args.landmarks else None
    composite_report = json.loads(args.composites.read_text()) if args.composites else None
    anatomy_report = json.loads(args.anatomy.read_text()) if args.anatomy else None
    report = run_structural_preflight(
        manifest,
        args.manifest.parent.parent,
        hand_in_core_scope=not args.hand_not_core,
        include_side_views=not args.exclude_side_views,
        landmark_report=landmark_report,
        composite_report=composite_report,
        anatomy_report=anatomy_report,
        manifest_sha256=manifest_hash,
    )
    report["input_manifest"] = str(args.manifest)
    report["input_manifest_sha256"] = manifest_hash
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["blocking_conditions"] else 0


if __name__ == "__main__":
    sys.exit(main())
