"""Unique local accounts, revocable sessions and security events."""

import sqlalchemy as sa
from alembic import op

revision = "0004_studio_accounts"
down_revision = "0003_studio_jobs"
branch_labels = None
depends_on = None


def created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True),
                     server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade():
    op.create_table(
        "studio_users", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)), created_at())
    op.create_table(
        "studio_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("studio_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), created_at())
    op.create_index("ix_studio_sessions_user_id", "studio_sessions", ["user_id"])
    op.create_table(
        "studio_security_events", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False), created_at())
    op.add_column("studio_jobs", sa.Column("created_by", sa.String(64),
                                          nullable=False, server_default="LOCAL_DEVELOPER"))
    op.add_column("studio_templates", sa.Column("created_by", sa.String(64),
                                               nullable=False, server_default="LOCAL_DEVELOPER"))


def downgrade():
    op.drop_column("studio_templates", "created_by")
    op.drop_column("studio_jobs", "created_by")
    op.drop_table("studio_security_events")
    op.drop_index("ix_studio_sessions_user_id", "studio_sessions")
    op.drop_table("studio_sessions")
    op.drop_table("studio_users")
