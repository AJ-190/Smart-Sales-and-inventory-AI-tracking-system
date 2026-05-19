"""fill approvals roles with pending

Revision ID: 1f240fd30bcc
Revises: 2fa6b9e76f0a
Create Date: 2026-05-19 11:22:24.023393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f240fd30bcc'
down_revision: Union[str, Sequence[str], None] = '2fa6b9e76f0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():

    op.execute("UPDATE approvals SET role = 'user' WHERE role IS NULL")
    

    op.alter_column('approvals', 'role', nullable=False)


def downgrade():
    op.drop_column('approvals', 'role')


