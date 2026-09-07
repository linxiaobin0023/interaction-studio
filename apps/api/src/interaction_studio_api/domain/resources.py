from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .enums import (
    AttemptState,
    DatasetKind,
    DatasetRunState,
    EvidenceStatus,
    FormalRunState,
    GateDecision,
    InteractionKind,
    OutputValidationStatus,
    PoseZone,
    ReviewDecision,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetContract(StrictContract):
    dataset_manifest_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    dataset_kind: DatasetKind
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    case_count: int = Field(ge=0)
    custodian: str = Field(min_length=1, max_length=200)
    frozen_at: AwareDatetime | None = None


class CaseContract(StrictContract):
    case_id: str = Field(min_length=1, max_length=128)
    dataset_manifest_id: str = Field(min_length=1, max_length=128)
    external_case_id: str = Field(min_length=1, max_length=128)
    interaction_kind: InteractionKind
    pose_zone: PoseZone
    case_base_sha256: str = Field(pattern=SHA256_PATTERN)
    build_id: str = Field(min_length=1, max_length=128)
    frozen: bool


class DatasetRunContract(StrictContract):
    dataset_run_id: str = Field(min_length=1, max_length=128)
    dataset_manifest_id: str = Field(min_length=1, max_length=128)
    build_id: str = Field(min_length=1, max_length=128)
    state: DatasetRunState
    resource_version: int = Field(ge=1)


class AttemptContract(StrictContract):
    attempt_id: str = Field(min_length=1, max_length=128)
    formal_run_id: str | None = None
    dataset_run_id: str | None = None
    case_id: str = Field(min_length=1, max_length=128)
    business_attempt_no: int = Field(ge=1, le=2)
    state: AttemptState
    request_hash: str = Field(pattern=SHA256_PATTERN)
    idempotency_key: str = Field(min_length=8, max_length=128)
    resource_version: int = Field(ge=1)
    infra_retry_count: int = Field(ge=0, le=2)
    failure_classification: str | None = None
    route_reason: str | None = None

    @model_validator(mode="after")
    def exactly_one_run(self) -> "AttemptContract":
        if (self.formal_run_id is None) == (self.dataset_run_id is None):
            raise ValueError("exactly one of formal_run_id and dataset_run_id is required")
        if self.formal_run_id is not None and self.state is AttemptState.CANCELLED:
            raise ValueError("Formal Attempt cannot be CANCELLED")
        return self


class OutputContract(StrictContract):
    output_id: str = Field(min_length=1, max_length=128)
    attempt_id: str = Field(min_length=1, max_length=128)
    object_key: str = Field(min_length=1, max_length=1024)
    object_version: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=SHA256_PATTERN)
    mime_type: str = Field(min_length=1, max_length=128)
    byte_size: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    validation_status: OutputValidationStatus
    object_lock_mode: str | None = None
    retention_until: AwareDatetime | None = None


class QCResultContract(StrictContract):
    qc_result_id: str = Field(min_length=1, max_length=128)
    formal_run_id: str = Field(min_length=1, max_length=128)
    output_id: str = Field(min_length=1, max_length=128)
    qc_protocol_version: str = Field(min_length=1, max_length=128)
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: ReviewDecision
    identity_pass: bool
    product_pass: bool
    interaction_pass: bool
    geometry_pass: bool
    artifact_pass: bool
    failure_codes: list[str]
    result_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def decision_matches_dimensions(self) -> "QCResultContract":
        all_pass = all(
            (
                self.identity_pass,
                self.product_pass,
                self.interaction_pass,
                self.geometry_pass,
                self.artifact_pass,
            )
        )
        if (self.decision is ReviewDecision.PASS) != all_pass:
            raise ValueError("PASS requires all five dimensions; otherwise decision must be FAIL")
        return self


class GateResultContract(StrictContract):
    gate_result_id: str = Field(min_length=1, max_length=128)
    gate_type: str = Field(min_length=1, max_length=64)
    threshold_version_id: str = Field(min_length=1, max_length=128)
    decision: GateDecision
    blocking_conditions: list[str]
    evidence_refs: list[str]
    signed_by: str | None = None
    signed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def signature_is_atomic(self) -> "GateResultContract":
        if (self.signed_by is None) != (self.signed_at is None):
            raise ValueError("signed_by and signed_at must be present or absent together")
        return self


class FormalRunContract(StrictContract):
    formal_run_id: str = Field(min_length=1, max_length=128)
    dataset_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    build_id: str = Field(min_length=1, max_length=128)
    qc_protocol_version: str = Field(min_length=1, max_length=128)
    analysis_spec_sha256: str = Field(pattern=SHA256_PATTERN)
    state: FormalRunState
    resource_version: int = Field(ge=1)
    invalidation_reason: str | None = None
    supersedes_run_id: str | None = None

    @model_validator(mode="after")
    def invalidation_has_reason(self) -> "FormalRunContract":
        invalidated = self.state is FormalRunState.INVALIDATED
        if invalidated != (self.invalidation_reason is not None):
            raise ValueError("invalidation_reason is required only for INVALIDATED state")
        if self.supersedes_run_id == self.formal_run_id:
            raise ValueError("FormalRun cannot supersede itself")
        return self


class EvidenceManifestContract(StrictContract):
    evidence_manifest_id: str = Field(min_length=1, max_length=128)
    formal_run_id: str = Field(min_length=1, max_length=128)
    case_id: str | None = None
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    chain_head_sha256: str = Field(pattern=SHA256_PATTERN)
    status: EvidenceStatus
    object_refs: list[str]
    object_lock_verified: bool

    @model_validator(mode="after")
    def ready_requires_lock(self) -> "EvidenceManifestContract":
        if self.status is EvidenceStatus.READY and not self.object_lock_verified:
            raise ValueError("READY evidence requires verified object locks")
        return self


class CoreResourceContractBundle(StrictContract):
    schema_version: str
    dataset: DatasetContract | None = None
    case: CaseContract | None = None
    dataset_run: DatasetRunContract | None = None
    attempt: AttemptContract | None = None
    output: OutputContract | None = None
    qc_result: QCResultContract | None = None
    gate_result: GateResultContract | None = None
    formal_run: FormalRunContract | None = None
    evidence_manifest: EvidenceManifestContract | None = None
