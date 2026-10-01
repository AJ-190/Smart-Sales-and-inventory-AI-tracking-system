"""add sent_at to reminders

Lets the daily dispatcher mark a reminder as delivered so the same SMS is
never sent twice.

Revision ID: b3d91f0c7a52
Revises: 69508208d6c2
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d91f0c7a52'
down_revision: Union[str, Sequence[str], None] = '69508208d6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reminders', sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reminders', 'sent_at')