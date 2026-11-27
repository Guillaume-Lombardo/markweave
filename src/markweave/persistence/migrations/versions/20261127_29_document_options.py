"""Persist document defaults and frozen job options.

Revision ID: 20261127_29
Revises: 20261126_28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261127_29"
down_revision: str | None = "20261126_28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_document_options",
        sa.Column("template_id", sa.String(36), primary_key=True),
        sa.Column("options", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
    )
    op.add_column(
        "conversion_jobs", sa.Column("document_options", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_table("template_document_options")
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"
    # Some supported SQLite versions need a table copy. Preserve triggers that
    # reference the original tables during the rename.
    triggers = (
        bind.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'trigger' AND sql IS NOT NULL ORDER BY name"
        ).all()
        if sqlite
        else []
    )
    for name, _ in triggers:
        quoted = bind.dialect.identifier_preparer.quote(name)
        op.execute(f"DROP TRIGGER {quoted}")
    with op.batch_alter_table(
        "conversion_jobs", recreate="always" if sqlite else "auto"
    ) as batch:
        batch.drop_column("document_options")
    for _, definition in triggers:
        op.execute(definition)
