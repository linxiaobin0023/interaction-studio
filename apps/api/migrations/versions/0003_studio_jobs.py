"""Durable Development render jobs, atomic output bundles and five-dimension QC."""

import sqlalchemy as sa
from alembic import op

revision = "0003_studio_jobs"
down_revision = "0002_studio_editing"
branch_labels = None
depends_on = None


def created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True),
                     server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade():
    op.create_table(
        "studio_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("case_id", sa.String(32), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("output_sha256", sa.String(64)), created_at(),
        sa.CheckConstraint("state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')",
                           name="ck_studio_job_state"),
        sa.CheckConstraint("execution_count BETWEEN 0 AND 3", name="ck_studio_job_executions"),
        sa.CheckConstraint("review_version >= 0", name="ck_studio_job_review_version"),
        sa.CheckConstraint("state <> 'SUCCEEDED' OR output_sha256 IS NOT NULL",
                           name="ck_studio_job_output"),
    )
    op.create_index("ix_studio_jobs_case_id", "studio_jobs", ["case_id"])
    op.create_index("ix_studio_jobs_state", "studio_jobs", ["state"])
    op.create_table(
        "studio_job_outputs",
        sa.Column("job_id", sa.String(36),
                  sa.ForeignKey("studio_jobs.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("bundle", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), created_at(),
    )
    op.create_table(
        "studio_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36),
                  sa.ForeignKey("studio_job_outputs.job_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False), created_at(),
        sa.UniqueConstraint("job_id", "version", name="uq_studio_review_version"),
        sa.CheckConstraint("version >= 1", name="ck_studio_review_version"),
    )
    op.create_index("ix_studio_reviews_job_id", "studio_reviews", ["job_id"])


def downgrade():
    op.drop_index("ix_studio_reviews_job_id", "studio_reviews")
    op.drop_table("studio_reviews")
    op.drop_table("studio_job_outputs")
    op.drop_index("ix_studio_jobs_state", "studio_jobs")
    op.drop_index("ix_studio_jobs_case_id", "studio_jobs")
    op.drop_table("studio_jobs")
