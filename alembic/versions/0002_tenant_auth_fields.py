"""tenant and auth audit fields

Revision ID: 0002_tenant_auth_fields
Revises: 0001_agent_os_records
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_tenant_auth_fields"
down_revision = "0001_agent_os_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_os_records", sa.Column("tenant_id", sa.String(length=255), nullable=True))
    op.create_index("ix_records_tenant_id", "agent_os_records", ["tenant_id"], unique=False)
    op.add_column("agent_os_session_events", sa.Column("tenant_id", sa.String(length=255), nullable=True))
    op.create_index("ix_events_tenant_id", "agent_os_session_events", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_events_tenant_id", table_name="agent_os_session_events")
    op.drop_column("agent_os_session_events", "tenant_id")
    op.drop_index("ix_records_tenant_id", table_name="agent_os_records")
    op.drop_column("agent_os_records", "tenant_id")
