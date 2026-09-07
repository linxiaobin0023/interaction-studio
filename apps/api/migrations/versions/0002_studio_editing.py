"""Add Development Studio drafts, append-only save history and versioned templates."""

import sqlalchemy as sa
from alembic import op

revision = "0002_studio_editing"
down_revision = "0001_core_contract"
branch_labels = None
depends_on = None


def created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True),
                     server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade():
    op.create_table(
        "studio_drafts",
        sa.Column("case_id", sa.String(32), primary_key=True),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("case_base_sha256", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False), created_at(),
        sa.CheckConstraint("resource_version >= 1", name="ck_studio_draft_version"),
    )
    op.create_table(
        "studio_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(32),
                  sa.ForeignKey("studio_drafts.case_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False), created_at(),
        sa.UniqueConstraint("case_id", "sequence_no", name="uq_studio_event_sequence"),
        sa.UniqueConstraint("event_hash", name="uq_studio_event_hash"),
        sa.CheckConstraint("sequence_no >= 1", name="ck_studio_event_sequence"),
    )
    op.create_index("ix_studio_events_case_id", "studio_events", ["case_id"])
    op.create_table(
        "studio_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("interaction", sa.String(32), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False), created_at(),
        sa.UniqueConstraint("name", "version", name="uq_studio_template_version"),
        sa.CheckConstraint("version >= 1", name="ck_studio_template_version"),
        sa.CheckConstraint("interaction IN ('MOUTH','NEAR_MOUTH','HAND_HELD')",
                           name="ck_studio_template_interaction"),
    )


def downgrade():
    op.drop_table("studio_templates")
    op.drop_index("ix_studio_events_case_id", "studio_events")
    op.drop_table("studio_events")
    op.drop_table("studio_drafts")
