"""Webhook delivery log for idempotency/replay protection

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE webhook_deliveries (
            delivery_id TEXT PRIMARY KEY,
            event TEXT NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_webhook_deliveries_received
            ON webhook_deliveries(received_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE webhook_deliveries")
