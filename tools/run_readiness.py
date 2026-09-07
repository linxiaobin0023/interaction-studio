"""Evaluate a local asset manifest against the frozen G0/G1 readiness baseline."""

import argparse
import json
import sys
from pathlib import Path

from interaction_studio_api.domain.readiness import (
    ReadinessEvaluationRequest,
    evaluate_readiness,
)
from pydantic import ValidationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--hand-not-core",
        action="store_true",
        help="Evaluate with Hand excluded from core scope; this is not a scope-change approval.",
    )
    parser.add_argument(
        "--exclude-side-views",
        action="store_true",
        help="Do not require ±90° product views; this is not a scope-change approval.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.manifest.read_text())
        request = ReadinessEvaluationRequest(
            manifest=payload,
            hand_in_core_scope=not args.hand_not_core,
            include_side_views=not args.exclude_side_views,
        )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    result = evaluate_readiness(request)
    print(result.model_dump_json(indent=2))
    return 1 if result.blocking_conditions else 0


if __name__ == "__main__":
    sys.exit(main())
