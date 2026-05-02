"""initial factorymind agentos records

Revision ID: 0001_agent_os_records
Revises:
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_agent_os_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_os_records",
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("agent_id", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("candidate_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_records_kind_key", "agent_os_records", ["kind", "key"], unique=True)
    op.create_index("ix_records_agent_id", "agent_os_records", ["agent_id"], unique=False)
    op.create_index("ix_records_session_id", "agent_os_records", ["session_id"], unique=False)
    op.create_index("ix_records_candidate_id", "agent_os_records", ["candidate_id"], unique=False)

    op.create_table(
        "agent_os_session_events",
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("agent_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_events_session_id", "agent_os_session_events", ["session_id"], unique=False)
    op.create_index("ix_events_event_id", "agent_os_session_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_events_event_id", table_name="agent_os_session_events")
    op.drop_index("ix_events_session_id", table_name="agent_os_session_events")
    op.drop_table("agent_os_session_events")
    op.drop_index("ix_records_candidate_id", table_name="agent_os_records")
    op.drop_index("ix_records_session_id", table_name="agent_os_records")
    op.drop_index("ix_records_agent_id", table_name="agent_os_records")
    op.drop_index("ix_records_kind_key", table_name="agent_os_records")
    op.drop_table("agent_os_records")
