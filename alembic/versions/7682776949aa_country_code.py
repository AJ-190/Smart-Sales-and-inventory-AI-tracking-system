"""country code

Revision ID: 7682776949aa
Revises: c1f2a9b7d4e6
Create Date: 2026-11-19 08:35:32.509880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7682776949aa'
down_revision: Union[str, Sequence[str], None] = 'c1f2a9b7d4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = sa.inspect(op.get_bind()).get_columns('users')
    if not any(column['name'] == 'country_code' for column in columns):
        op.add_column('users', sa.Column('country_code', sa.String(), nullable=True))
    op.execute("UPDATE users SET country_code = 'GH' WHERE country_code IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'country_code')
