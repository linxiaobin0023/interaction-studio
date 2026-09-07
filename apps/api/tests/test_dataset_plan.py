import importlib.util
import json
from pathlib import Path

TOOL_PATH = Path(__file__).parents[3] / "tools/validate_dataset_plan.py"
SPEC = importlib.util.spec_from_file_location("validate_dataset_plan", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_production_dataset_plan_is_valid_and_independent() -> None:
    project_root = Path(__file__).parents[3]
    plan = json.loads(
        (project_root / "datasets/registry/v1/dataset-plan.json").read_text()
    )

    assert MODULE.validate(plan) == []
    assert sum(item["case_count"] for item in plan["datasets"]) == 86
    assert len({item["prompt_family"] for item in plan["datasets"]}) == 4


def test_validation_cannot_be_unsealed() -> None:
    project_root = Path(__file__).parents[3]
    plan = json.loads(
        (project_root / "datasets/registry/v1/dataset-plan.json").read_text()
    )
    validation = next(item for item in plan["datasets"] if item["dataset"] == "VALIDATION")
    validation["sealed"] = False

    assert "VALIDATION: dataset must be sealed" in MODULE.validate(plan)
