"""Create repo_configs table

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE repo_configs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            repo_full_name TEXT NOT NULL UNIQUE,
            capabilities JSONB NOT NULL,
            installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            active BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE repo_configs")
