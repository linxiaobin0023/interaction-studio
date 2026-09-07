"""Create the G0 core domain contract.

Revision ID: 0001_core_contract
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_core_contract"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def id_column() -> sa.Column:
    return sa.Column("id", sa.String(length=36), nullable=False)


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        id_column(),
        sa.Column("name", sa.String(length=200), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "dataset_manifests",
        id_column(),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_kind", sa.String(length=32), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("distribution", sa.JSON(), nullable=False),
        sa.Column("custodian", sa.String(length=200), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.CheckConstraint("case_count >= 0", name="ck_dataset_manifest_case_count"),
        sa.CheckConstraint(
            "dataset_kind IN ('DEVELOPMENT','VALIDATION','FORMAL','GENERALIZATION',"
            "'REPAIR_POOL','REPAIR_EVALUATION','REPEATABILITY')",
            name="ck_dataset_manifest_kind",
        ),
        sa.CheckConstraint(
            "length(manifest_sha256) = 64", name="ck_dataset_manifest_hash_length"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "manifest_sha256", name="uq_dataset_manifest_hash"),
    )
    op.create_index("ix_dataset_manifests_project_id", "dataset_manifests", ["project_id"])
    op.create_table(
        "cases",
        id_column(),
        sa.Column("dataset_manifest_id", sa.String(length=36), nullable=False),
        sa.Column("external_case_id", sa.String(length=128), nullable=False),
        sa.Column("interaction_kind", sa.String(length=32), nullable=False),
        sa.Column("pose_zone", sa.String(length=16), nullable=False),
        sa.Column("case_base_sha256", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "interaction_kind IN ('MOUTH','NEAR_MOUTH','HAND_HELD')",
            name="ck_case_interaction_kind",
        ),
        sa.CheckConstraint("pose_zone IN ('GREEN','YELLOW','RED')", name="ck_case_pose_zone"),
        sa.CheckConstraint("length(case_base_sha256) = 64", name="ck_case_hash_length"),
        sa.ForeignKeyConstraint(
            ["dataset_manifest_id"], ["dataset_manifests.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_manifest_id", "external_case_id", name="uq_case_dataset_external_id"
        ),
    )
    op.create_index("ix_cases_dataset_manifest_id", "cases", ["dataset_manifest_id"])
    op.create_table(
        "dataset_runs",
        id_column(),
        sa.Column("dataset_manifest_id", sa.String(length=36), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "state IN ('DRAFT','RUNNING','COMPLETED','INVALIDATED')",
            name="ck_dataset_run_state",
        ),
        sa.CheckConstraint("resource_version >= 1", name="ck_dataset_run_resource_version"),
        sa.ForeignKeyConstraint(
            ["dataset_manifest_id"], ["dataset_manifests.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_runs_dataset_manifest_id", "dataset_runs", ["dataset_manifest_id"])
    op.create_table(
        "formal_runs",
        id_column(),
        sa.Column("dataset_manifest_id", sa.String(length=36), nullable=False),
        sa.Column("build_id", sa.String(length=128), nullable=False),
        sa.Column("qc_protocol_version", sa.String(length=128), nullable=False),
        sa.Column("analysis_spec_sha256", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("supersedes_run_id", sa.String(length=36), nullable=True),
        created_at_column(),
        sa.CheckConstraint("resource_version >= 1", name="ck_formal_run_resource_version"),
        sa.CheckConstraint(
            "state IN ('DRAFT','READY','RUNNING','REVIEW_PENDING','COMPLETED','INVALIDATED')",
            name="ck_formal_run_state",
        ),
        sa.CheckConstraint(
            "(state = 'INVALIDATED' AND invalidation_reason IS NOT NULL) OR "
            "(state <> 'INVALIDATED' AND invalidation_reason IS NULL)",
            name="ck_formal_run_invalidation_reason",
        ),
        sa.CheckConstraint(
            "length(analysis_spec_sha256) = 64", name="ck_formal_run_analysis_hash_length"
        ),
        sa.CheckConstraint(
            "supersedes_run_id IS NULL OR supersedes_run_id <> id",
            name="ck_formal_run_not_self_superseding",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_manifest_id"], ["dataset_manifests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supersedes_run_id"], ["formal_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_formal_runs_dataset_manifest_id", "formal_runs", ["dataset_manifest_id"])
    op.create_table(
        "attempts",
        id_column(),
        sa.Column("formal_run_id", sa.String(length=36), nullable=True),
        sa.Column("dataset_run_id", sa.String(length=36), nullable=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("business_attempt_no", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("infra_retry_count", sa.Integer(), nullable=False),
        sa.Column("failure_classification", sa.String(length=64), nullable=True),
        sa.Column("route_reason", sa.String(length=256), nullable=True),
        created_at_column(),
        sa.CheckConstraint(
            "(formal_run_id IS NOT NULL AND dataset_run_id IS NULL) OR "
            "(formal_run_id IS NULL AND dataset_run_id IS NOT NULL)",
            name="ck_attempt_exactly_one_run",
        ),
        sa.CheckConstraint("business_attempt_no IN (1, 2)", name="ck_attempt_business_no"),
        sa.CheckConstraint("infra_retry_count BETWEEN 0 AND 2", name="ck_attempt_retry_budget"),
        sa.CheckConstraint("resource_version >= 1", name="ck_attempt_resource_version"),
        sa.CheckConstraint(
            "state IN ('CREATED','PREPARED','INFERENCE_STARTED','INFERENCE_SUCCEEDED',"
            "'OUTPUT_PERSISTED','OUTPUT_VALIDATING','VALID_OUTPUT','RETRY_PENDING',"
            "'OUTPUT_VALIDATION_FAILED','SYSTEM_FAIL','CANCELLED')",
            name="ck_attempt_state",
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_attempt_request_hash_length"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_run_id"], ["dataset_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["formal_run_id"], ["formal_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "formal_run_id", "case_id", "business_attempt_no", name="uq_attempt_formal_business_no"
        ),
        sa.UniqueConstraint(
            "dataset_run_id",
            "case_id",
            "business_attempt_no",
            name="uq_attempt_dataset_business_no",
        ),
        sa.UniqueConstraint(
            "formal_run_id", "case_id", "idempotency_key", name="uq_attempt_formal_idempotency"
        ),
        sa.UniqueConstraint(
            "dataset_run_id", "case_id", "idempotency_key", name="uq_attempt_dataset_idempotency"
        ),
    )
    op.create_index("ix_attempts_case_id", "attempts", ["case_id"])
    op.create_index("ix_attempts_dataset_run_id", "attempts", ["dataset_run_id"])
    op.create_index("ix_attempts_formal_run_id", "attempts", ["formal_run_id"])
    op.create_table(
        "outputs",
        id_column(),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("object_version", sa.String(length=256), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column("object_lock_mode", sa.String(length=32), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.CheckConstraint("byte_size > 0", name="ck_output_byte_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_output_dimensions"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_output_hash_length"),
        sa.CheckConstraint(
            "validation_status IN ('PENDING','VALIDATING','VALID_OUTPUT','VALIDATION_FAILED')",
            name="ck_output_validation_status",
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", name="uq_output_attempt"),
        sa.UniqueConstraint("object_key", "object_version", name="uq_output_object_version"),
    )
    op.create_index("ix_outputs_attempt_id", "outputs", ["attempt_id"])
    op.create_table(
        "qc_results",
        id_column(),
        sa.Column("formal_run_id", sa.String(length=36), nullable=False),
        sa.Column("output_id", sa.String(length=36), nullable=False),
        sa.Column("qc_protocol_version", sa.String(length=128), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("identity_pass", sa.Boolean(), nullable=False),
        sa.Column("product_pass", sa.Boolean(), nullable=False),
        sa.Column("interaction_pass", sa.Boolean(), nullable=False),
        sa.Column("geometry_pass", sa.Boolean(), nullable=False),
        sa.Column("artifact_pass", sa.Boolean(), nullable=False),
        sa.Column("failure_codes", sa.JSON(), nullable=False),
        sa.Column("result_sha256", sa.String(length=64), nullable=False),
        created_at_column(),
        sa.CheckConstraint("decision IN ('PASS','FAIL')", name="ck_qc_decision"),
        sa.CheckConstraint(
            "(decision = 'PASS' AND identity_pass AND product_pass AND interaction_pass "
            "AND geometry_pass AND artifact_pass) OR "
            "(decision = 'FAIL' AND NOT (identity_pass AND product_pass AND interaction_pass "
            "AND geometry_pass AND artifact_pass))",
            name="ck_qc_decision_dimensions",
        ),
        sa.CheckConstraint("length(result_sha256) = 64", name="ck_qc_result_hash_length"),
        sa.ForeignKeyConstraint(["formal_run_id"], ["formal_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_id"], ["outputs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "formal_run_id", "output_id", "qc_protocol_version", name="uq_qc_formal_output_protocol"
        ),
    )
    op.create_index("ix_qc_results_formal_run_id", "qc_results", ["formal_run_id"])
    op.create_index("ix_qc_results_output_id", "qc_results", ["output_id"])
    op.create_table(
        "gate_threshold_versions",
        id_column(),
        sa.Column("gate_type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("metric", sa.String(length=256), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("sample_rule", sa.Text(), nullable=False),
        sa.Column("decision_rule", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gate_type", "version", name="uq_gate_threshold_type_version"),
    )
    op.create_table(
        "gate_results",
        id_column(),
        sa.Column("gate_type", sa.String(length=64), nullable=False),
        sa.Column("threshold_version_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("blocking_conditions", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("signed_by", sa.String(length=128), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.CheckConstraint(
            "decision IN ('PASS','CONDITIONAL','NO_GO')", name="ck_gate_decision"
        ),
        sa.CheckConstraint(
            "(signed_by IS NULL AND signed_at IS NULL) OR "
            "(signed_by IS NOT NULL AND signed_at IS NOT NULL)",
            name="ck_gate_signature_pair",
        ),
        sa.ForeignKeyConstraint(
            ["threshold_version_id"], ["gate_threshold_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gate_results_gate_type", "gate_results", ["gate_type"])
    op.create_table(
        "evidence_manifests",
        id_column(),
        sa.Column("formal_run_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("chain_head_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("object_refs", sa.JSON(), nullable=False),
        sa.Column("object_lock_verified", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.CheckConstraint(
            "length(manifest_sha256) = 64", name="ck_evidence_manifest_hash_length"
        ),
        sa.CheckConstraint(
            "length(chain_head_sha256) = 64", name="ck_evidence_chain_hash_length"
        ),
        sa.CheckConstraint(
            "status IN ('EVIDENCE_PENDING','READY','INVALID')", name="ck_evidence_status"
        ),
        sa.CheckConstraint(
            "status <> 'READY' OR object_lock_verified",
            name="ck_evidence_ready_requires_lock",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["formal_run_id"], ["formal_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formal_run_id", "manifest_sha256", name="uq_evidence_run_hash"),
    )
    op.create_index("ix_evidence_manifests_case_id", "evidence_manifests", ["case_id"])
    op.create_index("ix_evidence_manifests_formal_run_id", "evidence_manifests", ["formal_run_id"])
    op.create_table(
        "operation_events",
        id_column(),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("operator_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=False),
        sa.Column("delta", sa.JSON(), nullable=False),
        sa.Column("after_state", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        created_at_column(),
        sa.CheckConstraint("sequence_no >= 1", name="ck_operation_sequence"),
        sa.CheckConstraint("length(event_hash) = 64", name="ck_operation_event_hash_length"),
        sa.CheckConstraint(
            "previous_hash IS NULL OR length(previous_hash) = 64",
            name="ck_operation_previous_hash_length",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence_no", name="uq_operation_case_sequence"),
        sa.UniqueConstraint("event_hash", name="uq_operation_event_hash"),
    )
    op.create_index("ix_operation_events_case_id", "operation_events", ["case_id"])


def downgrade() -> None:
    for table_name in (
        "operation_events",
        "evidence_manifests",
        "gate_results",
        "gate_threshold_versions",
        "qc_results",
        "outputs",
        "attempts",
        "formal_runs",
        "dataset_runs",
        "cases",
        "dataset_manifests",
        "projects",
    ):
        op.drop_table(table_name)
