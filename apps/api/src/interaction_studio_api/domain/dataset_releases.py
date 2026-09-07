"""Read verified local release summaries without exposing sealed case content."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

ReleaseDataset = Literal["development", "validation"]


class DatasetReleaseSummary(BaseModel):
    dataset: ReleaseDataset
    version: str
    status: Literal["READY", "BLOCKED"]
    case_count: int = Field(ge=0)
    target_case_count: int = Field(gt=0)
    interaction_counts: dict[str, int]
    measured_pose_counts: dict[str, int]
    manifest_sha256: str
    seal_verified: bool
    storage_guarantee: Literal["LOCAL_HASH_SEAL_NOT_OBJECT_LOCK"]
    formal_eligible: Literal[False] = False
    full_implementation_allowed: Literal[False] = False
    blocking_conditions: list[str]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("unsafe evidence reference")
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def read_release(artifact_root: Path, dataset: ReleaseDataset) -> DatasetReleaseSummary:
    if dataset not in ("development", "validation"):
        raise ValueError("dataset content is not accessible through this endpoint")
    root = artifact_root / "datasets" / dataset / "v1"
    manifest_path = root / "snapshot-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    report_path = root / "evidence/admission.json"
    report = json.loads(report_path.read_text())
    seal = json.loads((root / "seal.json").read_text())
    manifest_hash = digest(manifest_path)
    valid = (
        manifest["dataset"] == dataset.upper() == report["dataset"] == seal["dataset"]
        and manifest_hash == seal["manifest_sha256"] == report["manifest_sha256"]
        and report["status"] == "READY" and not report["errors"]
        and bool(seal["evidence"])
    )
    bound = {}
    for ref in seal["evidence"]:
        path = local_path(artifact_root, ref["path"])
        bound[path] = ref["sha256"]
        valid = valid and digest(path) == ref["sha256"]
    for path in (manifest_path, report_path):
        valid = valid and bound.get(path.resolve()) == digest(path)
    for case in manifest["cases"]:
        path = local_path(root, case["path"])
        valid = valid and bound.get(path) == case["sha256"]
    return DatasetReleaseSummary(
        dataset=dataset, version=manifest["dataset_version"],
        status="READY" if valid else "BLOCKED",
        case_count=manifest["actual_case_count"], target_case_count=manifest["target_case_count"],
        interaction_counts=manifest["interaction_counts"],
        measured_pose_counts=report["measured_pose_counts"], manifest_sha256=manifest_hash,
        seal_verified=valid, storage_guarantee="LOCAL_HASH_SEAL_NOT_OBJECT_LOCK",
        blocking_conditions=[] if valid else ["DATASET_RELEASE_INTEGRITY_FAILED"],
    )
