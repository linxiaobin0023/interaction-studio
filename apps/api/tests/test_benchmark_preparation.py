import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "tools"))
benchmark = importlib.import_module("prepare_g2_benchmark")


def test_benchmark_uses_only_frozen_development_and_never_claims_inference():
    plan = benchmark.prepare(Path(__file__).parents[3])
    assert plan["source_dataset"] == "DEVELOPMENT"
    assert plan["formal_data_allowed"] is False
    assert plan["provider_execution_performed"] is False
    assert plan["gate_decision"] is None
    assert len({c["case_base"]["sha256"] for c in plan["cases"]}) == 12
    assert plan["interaction_counts"] == {"MOUTH": 5, "NEAR_MOUTH": 3, "HAND_HELD": 4}
    assert len(plan["repeatability"]["distinct_cases"]) == 5
    assert plan["repeatability"]["repeats_per_case"] == 5
    assert all(c["residual"]["within_gate"] for c in plan["cases"])
    assert all("PALM_NORMAL" in c["target_pose"]["method"]
               for c in plan["cases"] if c["interaction"] == "HAND_HELD")
