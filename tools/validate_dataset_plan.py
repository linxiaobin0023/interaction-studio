"""Validate dataset quotas, pose policy and cross-dataset prompt-family isolation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(plan: dict) -> list[str]:
    errors: list[str] = []
    families: list[str] = []
    for dataset in plan.get("datasets", []):
        name = dataset.get("dataset", "UNKNOWN")
        count = dataset.get("case_count")
        interactions = dataset.get("interaction_counts", {})
        poses = dataset.get("pose_counts", {})
        if sum(interactions.values()) != count:
            errors.append(f"{name}: interaction counts do not sum to case_count")
        if sum(poses.values()) != count:
            errors.append(f"{name}: pose counts do not sum to case_count")
        if poses.get("RED", 0) != 0:
            errors.append(f"{name}: Red cases are forbidden")
        if count and poses.get("YELLOW", 0) / count > 0.2:
            errors.append(f"{name}: Yellow ratio exceeds 20%")
        if name in {"VALIDATION", "FORMAL", "GENERALIZATION"} and not dataset.get(
            "sealed"
        ):
            errors.append(f"{name}: dataset must be sealed")
        families.append(dataset.get("prompt_family"))
    if len(set(families)) != len(families):
        errors.append("prompt_family must be unique across datasets")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    errors = validate(plan)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
