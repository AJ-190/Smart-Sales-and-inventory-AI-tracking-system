"""per-business barcode uniqueness

Revision ID: c1f2a9b7d4e6
Revises: 84f626205431
Create Date: 2026-11-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1f2a9b7d4e6'
down_revision: Union[str, Sequence[str], None] = '84f626205431'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.drop_constraint('products_barcode_key', 'products', type_='unique')
    op.create_unique_constraint(
        'uq_products_business_barcode', 'products', ['business_id', 'barcode']
    )
    op.create_index(
        'ix_products_business_barcode', 'products', ['business_id', 'barcode'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_products_business_barcode', table_name='products')
    op.drop_constraint('uq_products_business_barcode', 'products', type_='unique')
    op.create_unique_constraint('products_barcode_key', 'products', ['barcode'])
    op.drop_column('products', 'is_deleted')
