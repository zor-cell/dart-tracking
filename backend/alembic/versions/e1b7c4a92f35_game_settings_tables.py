"""game settings tables

Revision ID: e1b7c4a92f35
Revises: b6d2e9f41a73
Create Date: 2026-11-14 23:30:00.000000

One settings table per game variant instead of columns and JSON on `games`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e1b7c4a92f35'
down_revision: Union[str, Sequence[str], None] = 'b6d2e9f41a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _game_id() -> sa.Column:
    return sa.Column(
        "game_id", sa.Uuid(as_uuid=False), sa.ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
    )


def _finish() -> list[sa.Column]:
    return [
        sa.Column("catch_up", sa.Boolean(), nullable=False),
        sa.Column("play_on", sa.Boolean(), nullable=False),
    ]


def _points() -> list[sa.Column]:
    return [
        sa.Column("start_score", sa.Integer(), nullable=False),
        sa.Column("checkout_mode", sa.String(length=16), nullable=False),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("game_x01", _game_id(), *_points(), *_finish())
    op.create_table(
        "game_elimination",
        _game_id(),
        *_points(),
        sa.Column("kill", sa.String(length=16), nullable=False),
        *_finish(),
    )
    op.create_table(
        "game_cricket", _game_id(), sa.Column("scoring", sa.String(length=16), nullable=False)
    )
    op.create_table(
        "game_killer",
        _game_id(),
        sa.Column("numbers", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("lives", sa.Integer(), nullable=False),
        sa.Column("zone", sa.String(length=16), nullable=False),
    )
    op.create_table(
        "game_around_the_clock",
        _game_id(),
        sa.Column("zone", sa.String(length=16), nullable=False),
        sa.Column("skip", sa.Boolean(), nullable=False),
        *_finish(),
    )
    op.create_table(
        "game_training",
        _game_id(),
        sa.Column("goal", sa.String(length=16), nullable=False),
        sa.Column("ring", sa.String(length=16), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("repeats", sa.Integer(), nullable=False),
        sa.Column("shuffle", sa.Boolean(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
    )

    op.execute(
        """
        INSERT INTO game_x01 (game_id, start_score, checkout_mode, catch_up, play_on)
        SELECT id, mode, COALESCE(checkout_mode, 'double_out'), catch_up, play_on
        FROM games WHERE variant = 'x01'
        """
    )
    op.execute(
        """
        INSERT INTO game_elimination
            (game_id, start_score, checkout_mode, kill, catch_up, play_on)
        SELECT id, mode, COALESCE(checkout_mode, 'double_out'),
               COALESCE(options->>'kill', 'any'), catch_up, play_on
        FROM games WHERE variant = 'elimination'
        """
    )
    op.execute(
        """
        INSERT INTO game_cricket (game_id, scoring)
        SELECT id, COALESCE(options->>'scoring', 'standard')
        FROM games WHERE variant = 'cricket'
        """
    )
    op.execute(
        """
        INSERT INTO game_killer (game_id, numbers, lives, zone)
        SELECT g.id,
               COALESCE(
                   ARRAY(SELECT json_array_elements_text(g.options->'numbers')::int),
                   ARRAY(SELECT generate_series(
                       1, (SELECT count(*)::int FROM game_players p WHERE p.game_id = g.id)
                   ))
               ),
               COALESCE((g.options->>'lives')::int, 3),
               COALESCE(g.options->>'zone', 'double')
        FROM games g WHERE g.variant = 'killer'
        """
    )
    op.execute(
        """
        INSERT INTO game_around_the_clock (game_id, zone, skip, catch_up, play_on)
        SELECT id, COALESCE(options->>'zone', 'any'),
               COALESCE((options->>'skip')::boolean, false), catch_up, play_on
        FROM games WHERE variant = 'around_the_clock'
        """
    )
    op.execute(
        """
        INSERT INTO game_training (game_id, goal, ring, fields, repeats, shuffle, seed)
        SELECT id, COALESCE(options->>'goal', 'free'), COALESCE(options->>'ring', 'single'),
               COALESCE((options->'fields')::jsonb, '[]'::jsonb),
               COALESCE((options->>'repeats')::int, 1),
               COALESCE((options->>'shuffle')::boolean, false),
               COALESCE((options->>'seed')::int, 0)
        FROM games WHERE variant = 'training'
        """
    )

    for column in ("mode", "checkout_mode", "options", "catch_up", "play_on"):
        op.drop_column("games", column)


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("games", sa.Column("mode", sa.Integer(), nullable=True))
    op.add_column("games", sa.Column("checkout_mode", sa.String(length=16), nullable=True))
    op.add_column("games", sa.Column("options", sa.JSON(), nullable=True))
    for column in ("catch_up", "play_on"):
        op.add_column(
            "games", sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.false())
        )

    for table, kill in (("game_x01", "NULL"), ("game_elimination", "json_build_object('kill', s.kill)")):
        op.execute(
            f"""
            UPDATE games g SET mode = s.start_score, checkout_mode = s.checkout_mode,
                   catch_up = s.catch_up, play_on = s.play_on, options = {kill}
            FROM {table} s WHERE s.game_id = g.id
            """
        )
    op.execute(
        """
        UPDATE games g SET options = json_build_object('scoring', s.scoring)
        FROM game_cricket s WHERE s.game_id = g.id
        """
    )
    op.execute(
        """
        UPDATE games g SET options = json_build_object(
            'numbers', to_json(s.numbers), 'lives', s.lives, 'zone', s.zone)
        FROM game_killer s WHERE s.game_id = g.id
        """
    )
    op.execute(
        """
        UPDATE games g SET catch_up = s.catch_up, play_on = s.play_on,
               options = json_build_object('zone', s.zone, 'skip', s.skip)
        FROM game_around_the_clock s WHERE s.game_id = g.id
        """
    )
    op.execute(
        """
        UPDATE games g SET options = json_build_object(
            'goal', s.goal, 'ring', s.ring, 'fields', s.fields, 'repeats', s.repeats,
            'shuffle', s.shuffle, 'seed', s.seed)
        FROM game_training s WHERE s.game_id = g.id
        """
    )

    for table in (
        "game_training", "game_around_the_clock", "game_killer", "game_cricket",
        "game_elimination", "game_x01",
    ):
        op.drop_table(table)
