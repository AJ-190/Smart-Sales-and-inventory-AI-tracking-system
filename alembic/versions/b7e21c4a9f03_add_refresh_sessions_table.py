"""add refresh_sessions table

Revision ID: b7e21c4a9f03
Revises: 129e8d925b60
Create Date: 2026-10-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e21c4a9f03'
down_revision: Union[str, None] = '129e8d925b60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refresh_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_refresh_sessions_session_id', 'refresh_sessions', ['session_id'])
    op.create_index('ix_refresh_sessions_user_id', 'refresh_sessions', ['user_id'])
    op.create_index('ix_refresh_sessions_token_hash', 'refresh_sessions', ['token_hash'])

    # Carry every live refresh token over so nobody is signed out by the deploy.
    # session_id stays NULL: these tokens predate the sid claim and can only be
    # matched by hash. The first successful refresh fills it in.
    op.execute(
        sa.text(
            "INSERT INTO refresh_sessions (user_id, token_hash, created_at) "
            "SELECT user_id, refresh_token, NOW() FROM users "
            "WHERE refresh_token IS NOT NULL"
        )
    )


def downgrade() -> None:
    # Point every user back at their newest live session so the old
    # single-column lookup still resolves after a rollback.
    op.execute(
        sa.text(
            "UPDATE users SET refresh_token = ("
            "  SELECT token_hash FROM refresh_sessions "
            "  WHERE refresh_sessions.user_id = users.user_id "
            "  AND refresh_sessions.revoked_at IS NULL "
            "  ORDER BY refresh_sessions.created_at DESC LIMIT 1"
            ")"
        )
    )
    op.drop_index('ix_refresh_sessions_token_hash', table_name='refresh_sessions')
    op.drop_index('ix_refresh_sessions_user_id', table_name='refresh_sessions')
    op.drop_index('ix_refresh_sessions_session_id', table_name='refresh_sessions')
    op.drop_table('refresh_sessions')