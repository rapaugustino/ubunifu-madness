"""add player tables

Revision ID: b5c8d3e47f12
Revises: a3f7e2b91c04
Create Date: 2026-03-09 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c8d3e47f12'
down_revision: Union[str, None] = 'a3f7e2b91c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Players table
    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('espn_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('jersey', sa.String(length=5), nullable=True),
        sa.Column('position', sa.String(length=5), nullable=True),
        sa.Column('position_full', sa.String(length=30), nullable=True),
        sa.Column('height', sa.String(length=10), nullable=True),
        sa.Column('weight', sa.String(length=10), nullable=True),
        sa.Column('experience', sa.String(length=20), nullable=True),
        sa.Column('headshot_url', sa.String(length=500), nullable=True),
        sa.Column('gender', sa.String(length=1), nullable=False, server_default='M'),
        sa.Column('injury_status', sa.String(length=20), nullable=True),
        sa.Column('injury_detail', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('espn_id'),
    )
    op.create_index('ix_player_team', 'players', ['team_id'])
    op.create_index('ix_player_espn', 'players', ['espn_id'])

    # Player season stats
    op.create_table(
        'player_season_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('games_played', sa.Integer(), server_default='0'),
        sa.Column('minutes_total', sa.Float(), server_default='0'),
        sa.Column('points_total', sa.Integer(), server_default='0'),
        sa.Column('fgm', sa.Integer(), server_default='0'),
        sa.Column('fga', sa.Integer(), server_default='0'),
        sa.Column('fgm3', sa.Integer(), server_default='0'),
        sa.Column('fga3', sa.Integer(), server_default='0'),
        sa.Column('ftm', sa.Integer(), server_default='0'),
        sa.Column('fta', sa.Integer(), server_default='0'),
        sa.Column('oreb_total', sa.Integer(), server_default='0'),
        sa.Column('dreb_total', sa.Integer(), server_default='0'),
        sa.Column('reb_total', sa.Integer(), server_default='0'),
        sa.Column('ast_total', sa.Integer(), server_default='0'),
        sa.Column('to_total', sa.Integer(), server_default='0'),
        sa.Column('stl_total', sa.Integer(), server_default='0'),
        sa.Column('blk_total', sa.Integer(), server_default='0'),
        sa.Column('pf_total', sa.Integer(), server_default='0'),
        sa.Column('ppg', sa.Float(), server_default='0'),
        sa.Column('rpg', sa.Float(), server_default='0'),
        sa.Column('apg', sa.Float(), server_default='0'),
        sa.Column('mpg', sa.Float(), server_default='0'),
        sa.Column('fg_pct', sa.Float(), nullable=True),
        sa.Column('fg3_pct', sa.Float(), nullable=True),
        sa.Column('ft_pct', sa.Float(), nullable=True),
        sa.Column('minutes_share', sa.Float(), nullable=True),
        sa.Column('usage_rate', sa.Float(), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season', 'player_id', name='uq_player_stats_season'),
    )
    op.create_index('ix_player_stats_team_season', 'player_season_stats', ['team_id', 'season'])

    # Player game logs
    op.create_table(
        'player_game_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('espn_game_id', sa.String(length=20), nullable=False),
        sa.Column('game_date', sa.String(length=10), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Float(), server_default='0'),
        sa.Column('points', sa.Integer(), server_default='0'),
        sa.Column('fgm', sa.Integer(), server_default='0'),
        sa.Column('fga', sa.Integer(), server_default='0'),
        sa.Column('fgm3', sa.Integer(), server_default='0'),
        sa.Column('fga3', sa.Integer(), server_default='0'),
        sa.Column('ftm', sa.Integer(), server_default='0'),
        sa.Column('fta', sa.Integer(), server_default='0'),
        sa.Column('oreb', sa.Integer(), server_default='0'),
        sa.Column('dreb', sa.Integer(), server_default='0'),
        sa.Column('reb', sa.Integer(), server_default='0'),
        sa.Column('ast', sa.Integer(), server_default='0'),
        sa.Column('to', sa.Integer(), server_default='0'),
        sa.Column('stl', sa.Integer(), server_default='0'),
        sa.Column('blk', sa.Integer(), server_default='0'),
        sa.Column('pf', sa.Integer(), server_default='0'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'espn_game_id', name='uq_player_game'),
    )
    op.create_index('ix_pgl_game', 'player_game_logs', ['espn_game_id'])
    op.create_index('ix_pgl_player_season', 'player_game_logs', ['player_id', 'season'])


def downgrade() -> None:
    op.drop_index('ix_pgl_player_season', table_name='player_game_logs')
    op.drop_index('ix_pgl_game', table_name='player_game_logs')
    op.drop_table('player_game_logs')
    op.drop_index('ix_player_stats_team_season', table_name='player_season_stats')
    op.drop_table('player_season_stats')
    op.drop_index('ix_player_espn', table_name='players')
    op.drop_index('ix_player_team', table_name='players')
    op.drop_table('players')
