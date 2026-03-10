"""add game_predictions table

Revision ID: a3f7e2b91c04
Revises: d14585130274
Create Date: 2026-03-09 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7e2b91c04'
down_revision: Union[str, None] = 'd14585130274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'game_predictions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('espn_game_id', sa.String(length=20), nullable=False),
        sa.Column('game_date', sa.String(length=10), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('gender', sa.String(length=1), nullable=False),
        sa.Column('away_team_id', sa.Integer(), nullable=True),
        sa.Column('home_team_id', sa.Integer(), nullable=True),
        sa.Column('away_name', sa.String(length=100), nullable=True),
        sa.Column('home_name', sa.String(length=100), nullable=True),
        sa.Column('locked_prob_away', sa.Float(), nullable=False),
        sa.Column('locked_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('prediction_source', sa.String(length=20), nullable=False),
        sa.Column('away_score', sa.Integer(), nullable=True),
        sa.Column('home_score', sa.Integer(), nullable=True),
        sa.Column('winner_team_id', sa.Integer(), nullable=True),
        sa.Column('model_correct', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['away_team_id'], ['teams.id']),
        sa.ForeignKeyConstraint(['home_team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('espn_game_id', name='uq_game_pred_espn'),
    )
    op.create_index('ix_game_pred_date', 'game_predictions', ['game_date'])
    op.create_index('ix_game_pred_season_gender', 'game_predictions', ['season', 'gender'])


def downgrade() -> None:
    op.drop_index('ix_game_pred_season_gender', table_name='game_predictions')
    op.drop_index('ix_game_pred_date', table_name='game_predictions')
    op.drop_table('game_predictions')
