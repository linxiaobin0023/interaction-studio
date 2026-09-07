import importlib.util
import json
from pathlib import Path

TOOL_PATH = Path(__file__).parents[3] / "tools/verify_gate_result.py"
SPEC = importlib.util.spec_from_file_location("verify_gate_result", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_g0_gate_evidence_hashes_are_valid() -> None:
    project_root = Path(__file__).parents[3]
    result = project_root / "docs/gates/G0-result-v1.json"

    assert MODULE.verify(result, project_root) == []


def test_gate_verifier_rejects_hash_mismatch(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[3]
    source = json.loads((project_root / "docs/gates/G0-result-v1.json").read_text())
    source["evidence"][0]["sha256"] = "0" * 64
    result = tmp_path / "gate.json"
    result.write_text(json.dumps(source))

    assert "evidence hash mismatch" in MODULE.verify(result, project_root)[0]
