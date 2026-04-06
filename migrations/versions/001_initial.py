"""Initial migration: create notifications table."""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "sending",
                "sent",
                "failed",
                "dead_letter",
                name="notificationstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_notifications_recipient_email", "notifications", ["recipient_email"])
    op.create_index("ix_notifications_status", "notifications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_recipient_email", table_name="notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notificationstatus")
