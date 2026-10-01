"""replace reminder start/end dates with a single date

Revision ID: 12858f7b0437
Revises: b7f4c9a2e1d0
Create Date: 2026-10-01 17:35:13.212969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '12858f7b0437'
down_revision: Union[str, Sequence[str], None] = 'b7f4c9a2e1d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add `date` as nullable first: adding a NOT NULL column with no default
    #    fails on any table that already has rows.
    op.add_column(
        "reminders",
        sa.Column("date", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )

    # 2. Backfill existing rows: prefer start_date, fall back to end_date,
    #    otherwise stamp now(). Split into two statements because the simple
    #    form leaves start_date = end_date = NULL on conflict.
    op.execute(
        """
        UPDATE reminders
           SET date = COALESCE(start_date, end_date)
         WHERE start_date IS NOT NULL OR end_date IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE reminders
           SET date = now()
         WHERE date IS NULL
        """
    )

    # 3. Now that every row has a value, enforce the model constraint.
    op.alter_column(
        "reminders",
        "date",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
    )

    # 4. Drop the old range columns.
    op.drop_column("reminders", "start_date")
    op.drop_column("reminders", "end_date")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "reminders",
        sa.Column("start_date", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("end_date", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )

    # Restore the old range from the single date. A single date has no range,
    # so start_date and end_date both collapse to the same value.
    op.execute("UPDATE reminders SET start_date = date WHERE start_date IS NULL")
    op.execute("UPDATE reminders SET end_date = date WHERE end_date IS NULL")

    op.drop_column("reminders", "date")
