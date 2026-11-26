"""Persist confirmed conversion sizes and result warnings.

Revision ID: 20261126_28
Revises: 20261021_27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_28"
down_revision: str | None = "20261021_27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversion_jobs",
        sa.Column(
            "large_archive_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "conversion_jobs",
        sa.Column("warnings", sa.String(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "conversion_size_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sizes", sa.String(), nullable=False),
    )
    op.create_index(
        "ix_conversion_size_audit_retention",
        "conversion_size_audit",
        ["created_at", "id"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER conversion_size_audit_immutable_update "
            "BEFORE UPDATE ON conversion_size_audit "
            "BEGIN SELECT RAISE(ABORT, 'immutable conversion audit'); END"
        )
        op.execute(
            "CREATE TRIGGER conversion_size_audit_immutable_delete "
            "BEFORE DELETE ON conversion_size_audit "
            "WHEN NOT EXISTS (SELECT 1 FROM audit_cleanup_guards) "
            "BEGIN SELECT RAISE(ABORT, 'immutable conversion audit'); END"
        )
    else:
        op.execute(
            "CREATE TRIGGER conversion_size_audit_immutable_update "
            "BEFORE UPDATE ON conversion_size_audit "
            "FOR EACH ROW EXECUTE FUNCTION reject_composer_record_mutation()"
        )
        op.execute(
            "CREATE TRIGGER conversion_size_audit_immutable_delete "
            "BEFORE DELETE ON conversion_size_audit "
            "FOR EACH ROW EXECUTE FUNCTION reject_unauthorized_audit_delete()"
        )


def downgrade() -> None:
    op.drop_table("conversion_size_audit")
    op.drop_column("conversion_jobs", "warnings")
    op.drop_column("conversion_jobs", "large_archive_confirmed")
