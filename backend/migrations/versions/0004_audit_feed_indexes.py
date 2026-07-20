"""Indexes serving the id-ordered audit feed queries

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The audit feed filters by repo/org and orders/paginates on id
    # (append-only table: id order tracks created_at order).
    op.execute(
        """
        CREATE INDEX idx_audit_events_repo_id ON audit_events(repository_id, id);
        CREATE INDEX idx_audit_events_org_id ON audit_events(organization_id, id);
        DROP INDEX idx_audit_events_org_created;
        DROP INDEX idx_audit_events_repo_created;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE INDEX idx_audit_events_org_created
            ON audit_events(organization_id, created_at);
        CREATE INDEX idx_audit_events_repo_created
            ON audit_events(repository_id, created_at);
        DROP INDEX idx_audit_events_repo_id;
        DROP INDEX idx_audit_events_org_id;
        """
    )
