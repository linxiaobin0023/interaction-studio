from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .domain.enums import (
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


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class DatasetManifestRecord(TimestampMixin, Base):
    __tablename__ = "dataset_manifests"
    __table_args__ = (
        UniqueConstraint("project_id", "manifest_sha256", name="uq_dataset_manifest_hash"),
        CheckConstraint("case_count >= 0", name="ck_dataset_manifest_case_count"),
        CheckConstraint(
            "dataset_kind IN ('DEVELOPMENT','VALIDATION','FORMAL','GENERALIZATION',"
            "'REPAIR_POOL','REPAIR_EVALUATION','REPEATABILITY')",
            name="ck_dataset_manifest_kind",
        ),
        CheckConstraint("length(manifest_sha256) = 64", name="ck_dataset_manifest_hash_length"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dataset_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distribution: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    custodian: Mapped[str] = mapped_column(String(200), nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseRecord(TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint(
            "dataset_manifest_id", "external_case_id", name="uq_case_dataset_external_id"
        ),
        CheckConstraint(
            "interaction_kind IN ('MOUTH','NEAR_MOUTH','HAND_HELD')",
            name="ck_case_interaction_kind",
        ),
        CheckConstraint("pose_zone IN ('GREEN','YELLOW','RED')", name="ck_case_pose_zone"),
        CheckConstraint("length(case_base_sha256) = 64", name="ck_case_hash_length"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_manifest_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_manifests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    external_case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    interaction_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    pose_zone: Mapped[str] = mapped_column(String(16), nullable=False)
    case_base_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DatasetRun(TimestampMixin, Base):
    __tablename__ = "dataset_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT','RUNNING','COMPLETED','INVALIDATED')",
            name="ck_dataset_run_state",
        ),
        CheckConstraint("resource_version >= 1", name="ck_dataset_run_resource_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_manifest_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_manifests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DatasetRunState.DRAFT.value
    )
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class FormalRun(TimestampMixin, Base):
    __tablename__ = "formal_runs"
    __table_args__ = (
        CheckConstraint("resource_version >= 1", name="ck_formal_run_resource_version"),
        CheckConstraint(
            "state IN ('DRAFT','READY','RUNNING','REVIEW_PENDING','COMPLETED','INVALIDATED')",
            name="ck_formal_run_state",
        ),
        CheckConstraint(
            "(state = 'INVALIDATED' AND invalidation_reason IS NOT NULL) OR "
            "(state <> 'INVALIDATED' AND invalidation_reason IS NULL)",
            name="ck_formal_run_invalidation_reason",
        ),
        CheckConstraint(
            "length(analysis_spec_sha256) = 64", name="ck_formal_run_analysis_hash_length"
        ),
        CheckConstraint(
            "supersedes_run_id IS NULL OR supersedes_run_id <> id",
            name="ck_formal_run_not_self_superseding",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_manifest_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_manifests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    qc_protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_spec_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FormalRunState.DRAFT.value
    )
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    invalidation_reason: Mapped[str | None] = mapped_column(Text)
    supersedes_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("formal_runs.id", ondelete="RESTRICT")
    )


class Attempt(TimestampMixin, Base):
    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint(
            "(formal_run_id IS NOT NULL AND dataset_run_id IS NULL) OR "
            "(formal_run_id IS NULL AND dataset_run_id IS NOT NULL)",
            name="ck_attempt_exactly_one_run",
        ),
        CheckConstraint("business_attempt_no IN (1, 2)", name="ck_attempt_business_no"),
        CheckConstraint("infra_retry_count BETWEEN 0 AND 2", name="ck_attempt_retry_budget"),
        CheckConstraint("resource_version >= 1", name="ck_attempt_resource_version"),
        CheckConstraint(
            "state IN ('CREATED','PREPARED','INFERENCE_STARTED','INFERENCE_SUCCEEDED',"
            "'OUTPUT_PERSISTED','OUTPUT_VALIDATING','VALID_OUTPUT','RETRY_PENDING',"
            "'OUTPUT_VALIDATION_FAILED','SYSTEM_FAIL','CANCELLED')",
            name="ck_attempt_state",
        ),
        CheckConstraint("length(request_hash) = 64", name="ck_attempt_request_hash_length"),
        UniqueConstraint(
            "formal_run_id",
            "case_id",
            "business_attempt_no",
            name="uq_attempt_formal_business_no",
        ),
        UniqueConstraint(
            "dataset_run_id",
            "case_id",
            "business_attempt_no",
            name="uq_attempt_dataset_business_no",
        ),
        UniqueConstraint(
            "formal_run_id", "case_id", "idempotency_key", name="uq_attempt_formal_idempotency"
        ),
        UniqueConstraint(
            "dataset_run_id", "case_id", "idempotency_key", name="uq_attempt_dataset_idempotency"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    formal_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("formal_runs.id", ondelete="RESTRICT"), index=True
    )
    dataset_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_runs.id", ondelete="RESTRICT"), index=True
    )
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AttemptState.CREATED.value
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    infra_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_classification: Mapped[str | None] = mapped_column(String(64))
    route_reason: Mapped[str | None] = mapped_column(String(256))


class Output(TimestampMixin, Base):
    __tablename__ = "outputs"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_output_attempt"),
        UniqueConstraint("object_key", "object_version", name="uq_output_object_version"),
        CheckConstraint("byte_size > 0", name="ck_output_byte_size"),
        CheckConstraint("width > 0 AND height > 0", name="ck_output_dimensions"),
        CheckConstraint("length(sha256) = 64", name="ck_output_hash_length"),
        CheckConstraint(
            "validation_status IN ('PENDING','VALIDATING','VALID_OUTPUT','VALIDATION_FAILED')",
            name="ck_output_validation_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    object_version: Mapped[str] = mapped_column(String(256), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OutputValidationStatus.PENDING.value
    )
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    object_lock_mode: Mapped[str | None] = mapped_column(String(32))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QCResult(TimestampMixin, Base):
    __tablename__ = "qc_results"
    __table_args__ = (
        UniqueConstraint(
            "formal_run_id",
            "output_id",
            "qc_protocol_version",
            name="uq_qc_formal_output_protocol",
        ),
        CheckConstraint("decision IN ('PASS','FAIL')", name="ck_qc_decision"),
        CheckConstraint(
            "(decision = 'PASS' AND identity_pass AND product_pass AND interaction_pass "
            "AND geometry_pass AND artifact_pass) OR "
            "(decision = 'FAIL' AND NOT (identity_pass AND product_pass AND interaction_pass "
            "AND geometry_pass AND artifact_pass))",
            name="ck_qc_decision_dimensions",
        ),
        CheckConstraint("length(result_sha256) = 64", name="ck_qc_result_hash_length"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    formal_run_id: Mapped[str] = mapped_column(
        ForeignKey("formal_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    output_id: Mapped[str] = mapped_column(
        ForeignKey("outputs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qc_protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    identity_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    product_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    interaction_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    geometry_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    artifact_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class GateThresholdVersion(TimestampMixin, Base):
    __tablename__ = "gate_threshold_versions"
    __table_args__ = (
        UniqueConstraint("gate_type", "version", name="uq_gate_threshold_type_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    metric: Mapped[str] = mapped_column(String(256), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    sample_rule: Mapped[str] = mapped_column(Text, nullable=False)
    decision_rule: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GateResult(TimestampMixin, Base):
    __tablename__ = "gate_results"
    __table_args__ = (
        CheckConstraint("decision IN ('PASS','CONDITIONAL','NO_GO')", name="ck_gate_decision"),
        CheckConstraint(
            "(signed_by IS NULL AND signed_at IS NULL) OR "
            "(signed_by IS NOT NULL AND signed_at IS NOT NULL)",
            name="ck_gate_signature_pair",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    threshold_version_id: Mapped[str] = mapped_column(
        ForeignKey("gate_threshold_versions.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    blocking_conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    signed_by: Mapped[str | None] = mapped_column(String(128))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceManifest(TimestampMixin, Base):
    __tablename__ = "evidence_manifests"
    __table_args__ = (
        UniqueConstraint("formal_run_id", "manifest_sha256", name="uq_evidence_run_hash"),
        CheckConstraint("length(manifest_sha256) = 64", name="ck_evidence_manifest_hash_length"),
        CheckConstraint("length(chain_head_sha256) = 64", name="ck_evidence_chain_hash_length"),
        CheckConstraint(
            "status IN ('EVIDENCE_PENDING','READY','INVALID')",
            name="ck_evidence_status",
        ),
        CheckConstraint(
            "status <> 'READY' OR object_lock_verified",
            name="ck_evidence_ready_requires_lock",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    formal_run_id: Mapped[str] = mapped_column(
        ForeignKey("formal_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_head_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EvidenceStatus.EVIDENCE_PENDING.value
    )
    object_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    object_lock_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OperationEvent(TimestampMixin, Base):
    __tablename__ = "operation_events"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_no", name="uq_operation_case_sequence"),
        UniqueConstraint("event_hash", name="uq_operation_event_hash"),
        CheckConstraint("sequence_no >= 1", name="ck_operation_sequence"),
        CheckConstraint("length(event_hash) = 64", name="ck_operation_event_hash_length"),
        CheckConstraint(
            "previous_hash IS NULL OR length(previous_hash) = 64",
            name="ck_operation_previous_hash_length",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    delta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    after_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)


# Import-time assertions keep persisted values aligned with the public domain enums.
PERSISTED_ENUMS = {
    "dataset_kind": tuple(item.value for item in DatasetKind),
    "dataset_run_state": tuple(item.value for item in DatasetRunState),
    "interaction_kind": tuple(item.value for item in InteractionKind),
    "pose_zone": tuple(item.value for item in PoseZone),
    "attempt_state": tuple(item.value for item in AttemptState),
    "formal_run_state": tuple(item.value for item in FormalRunState),
    "output_validation_status": tuple(item.value for item in OutputValidationStatus),
    "gate_decision": tuple(item.value for item in GateDecision),
    "review_decision": tuple(item.value for item in ReviewDecision),
    "evidence_status": tuple(item.value for item in EvidenceStatus),
}


class StudioDraft(TimestampMixin, Base):
    """Development editing state, separate from production Case/Attempt records."""

    __tablename__ = "studio_drafts"
    __table_args__ = (
        CheckConstraint("resource_version >= 1", name="ck_studio_draft_version"),
    )
    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    case_base_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)


class StudioEvent(TimestampMixin, Base):
    __tablename__ = "studio_events"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_no", name="uq_studio_event_sequence"),
        UniqueConstraint("event_hash", name="uq_studio_event_hash"),
        CheckConstraint("sequence_no >= 1", name="ck_studio_event_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("studio_drafts.case_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class StudioTemplate(TimestampMixin, Base):
    created_by: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="LOCAL_DEVELOPER")
    __tablename__ = "studio_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_studio_template_version"),
        CheckConstraint("version >= 1", name="ck_studio_template_version"),
        CheckConstraint("interaction IN ('MOUTH','NEAR_MOUTH','HAND_HELD')",
                        name="ck_studio_template_interaction"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    interaction: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class StudioJob(TimestampMixin, Base):
    """Durable local rendering queue; never a provider or Formal attempt."""

    created_by: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="LOCAL_DEVELOPER")
    __tablename__ = "studio_jobs"
    __table_args__ = (
        CheckConstraint("state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')",
                        name="ck_studio_job_state"),
        CheckConstraint("execution_count BETWEEN 0 AND 3", name="ck_studio_job_executions"),
        CheckConstraint("review_version >= 0", name="ck_studio_job_review_version"),
        CheckConstraint("state <> 'SUCCEEDED' OR output_sha256 IS NOT NULL",
                        name="ck_studio_job_output"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    case_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    sources: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED", index=True)
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    output_sha256: Mapped[str | None] = mapped_column(String(64))


class StudioJobOutput(TimestampMixin, Base):
    __tablename__ = "studio_job_outputs"
    job_id: Mapped[str] = mapped_column(
        ForeignKey("studio_jobs.id", ondelete="RESTRICT"), primary_key=True)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    bundle: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class StudioReview(TimestampMixin, Base):
    __tablename__ = "studio_reviews"
    __table_args__ = (
        UniqueConstraint("job_id", "version", name="uq_studio_review_version"),
        CheckConstraint("version >= 1", name="ck_studio_review_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("studio_job_outputs.job_id", ondelete="RESTRICT"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class StudioUser(TimestampMixin, Base):
    __tablename__ = "studio_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    roles: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudioSession(TimestampMixin, Base):
    __tablename__ = "studio_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("studio_users.id", ondelete="RESTRICT"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StudioSecurityEvent(TimestampMixin, Base):
    __tablename__ = "studio_security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
