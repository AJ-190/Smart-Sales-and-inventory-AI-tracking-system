"""business chat tables

Revision ID: b7f4c9a2e1d0
Revises: f5530c9d7e8b
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f4c9a2e1d0'
down_revision: Union[str, Sequence[str], None] = '1ae6adc6389a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('group_chat_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('business_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.Text(), server_default='', nullable=False),
    sa.Column('attachment_type', sa.String(), nullable=True),
    sa.Column('attachment_url', sa.String(), nullable=True),
    sa.Column('attachment_name', sa.String(), nullable=True),
    sa.Column('attachment_size', sa.BigInteger(), nullable=True),
    sa.Column('is_edited', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.business_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_group_chat_messages_business_created', 'group_chat_messages', ['business_id', 'created_at'], unique=False)
    op.create_index('ix_group_chat_messages_user_id', 'group_chat_messages', ['user_id'], unique=False)

    op.create_table('chat_read_positions',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('business_id', sa.Integer(), nullable=False),
    sa.Column('last_read_message_id', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.business_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'business_id'),
    sa.UniqueConstraint('user_id', 'business_id', name='uq_chat_read_position')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chat_read_positions')
    op.drop_index('ix_group_chat_messages_user_id', table_name='group_chat_messages')
    op.drop_index('ix_group_chat_messages_business_created', table_name='group_chat_messages')
    op.drop_table('group_chat_messages')