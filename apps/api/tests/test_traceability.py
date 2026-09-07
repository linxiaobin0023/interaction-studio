import json
from pathlib import Path


def test_p0_traceability_matrix_is_complete_and_unique() -> None:
    project_root = Path(__file__).parents[3]
    path = project_root / "docs/traceability/p0-traceability.json"
    matrix = json.loads(path.read_text())
    requirements = matrix["requirements"]
    ids = [item["requirement_id"] for item in requirements]

    assert len(ids) == len(set(ids))
    assert len(requirements) >= 10
    for item in requirements:
        assert set(item) == {
            "requirement_id",
            "source",
            "implementation",
            "tests",
            "gate_result_id",
            "evidence",
            "status",
        }
        assert item["requirement_id"].startswith("P0-")


def test_traceability_does_not_reintroduce_removed_tco_scope() -> None:
    project_root = Path(__file__).parents[3]
    contents = (project_root / "docs/traceability/p0-traceability.json").read_text()

    assert "TCO" not in contents.upper()
