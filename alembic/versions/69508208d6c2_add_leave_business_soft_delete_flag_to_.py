"""add leave_business soft-delete flag to business_members

Revision ID: 69508208d6c2
Revises: 12858f7b0437
Create Date: 2026-10-01 18:12:47.618822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69508208d6c2'
down_revision: Union[str, Sequence[str], None] = '12858f7b0437'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The column does not exist yet, so this is an ADD, not an ALTER.
    # Mirrors src/users/models.py:47 -> `leave_business = Column(Boolean, default=False)`.
    # `default=False` in the model is a *client-side* default, not a server
    # default, so no server_default is declared here -- adding one would show
    # up as permanent drift in `alembic check`.
    op.add_column(
        "business_members",
        sa.Column("leave_business", sa.Boolean(), nullable=True),
    )

    # Data backfill only -- no schema change, so no new drift. Existing members
    # have not left, so they should read as false rather than NULL.
    op.execute("UPDATE business_members SET leave_business = false WHERE leave_business IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("business_members", "leave_business")
