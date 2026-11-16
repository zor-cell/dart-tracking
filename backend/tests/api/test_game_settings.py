import pytest
from alembic import command

from tests.api.support import alembic_config

TABLES = {
    "x01": "game_x01",
    "elimination": "game_elimination",
    "cricket": "game_cricket",
    "killer": "game_killer",
    "around_the_clock": "game_around_the_clock",
    "training": "game_training",
}
SETTINGS = [
    {"variant": "x01", "mode": 501, "checkoutMode": "single_out", "catchUp": True},
    {"variant": "elimination", "mode": 301, "kill": "double"},
    {"variant": "cricket", "scoring": "cut_throat"},
    {"variant": "killer", "lives": 5, "zone": "triple"},
    {"variant": "around_the_clock", "zone": "double", "playOn": True},
    {
        "variant": "training",
        "goal": "fields",
        "fields": [{"value": 19, "multiplier": 3}],
        "anyRing": True,
        "darts": 90,
    },
]
GUESTS = [{"name": "Ann"}, {"name": "Ben"}, {"name": "Cid"}]


@pytest.mark.parametrize("settings", SETTINGS, ids=lambda settings: settings["variant"])
def test_settings_are_stored_in_the_table_of_their_variant_alone(anon, session, settings):
    game = anon.new_game(*GUESTS, settings=settings)

    for variant, table in TABLES.items():
        rows = session.sql(f"SELECT game_id FROM {table}")
        assert len(rows) == (variant == settings["variant"])
    stored = anon.get(f"/games/{game['id']}").json()["settings"]
    assert stored == game["settings"]
    assert settings.items() <= stored.items()


def test_killer_keeps_the_dealt_numbers_by_seat(anon, session):
    game = anon.new_game(*GUESTS, settings={"variant": "killer"})

    (numbers,) = session.sql("SELECT numbers FROM game_killer")[0]

    assert numbers == [player["number"] for player in game["standing"]["players"]]


def test_deleting_a_game_drops_its_settings(anon, session):
    game = anon.new_game(*GUESTS, settings={"variant": "cricket"})

    session.sql("DELETE FROM games WHERE id = :id", id=game["id"])

    assert session.sql("SELECT game_id FROM game_cricket") == []


def test_every_dart_is_stored_with_the_field_it_was_thrown_at(anon, session):
    game = anon.new_game({"name": "Ann"}, settings={"variant": "around_the_clock", "zone": "double"})

    session.play(game["id"], [(1, 2), (2, 1), (2, 2)], hand_over=False)

    targets = session.sql(
        "SELECT target_value, target_multiplier FROM game_darts ORDER BY turn_index, dart_index"
    )
    assert [tuple(row) for row in targets] == [(1, 2), (2, 2), (2, 2)]


def test_the_migrations_move_stored_games_into_the_settings_tables(session):
    config = alembic_config()
    command.downgrade(config, "b6d2e9f41a73")
    try:
        games = {
            "x01": "501, 'single_out', NULL, true",
            "elimination": "301, 'double_out', NULL, false",
            "cricket": "NULL, NULL, '{\"scoring\": \"no_score\"}', false",
            "killer": "NULL, NULL, '{\"numbers\": [7, 12], \"lives\": 5, \"zone\": \"any\"}', false",
            "around_the_clock": "NULL, NULL, '{\"zone\": \"double\", \"skip\": false}', false",
            "training": "NULL, NULL, '{\"goal\": \"fields\", \"ring\": \"single\","
            " \"fields\": [[19, 3]], \"seed\": 7}', false",
        }
        ids = {}
        for variant, values in games.items():
            ids[variant] = session.sql(
                "INSERT INTO games (variant, mode, checkout_mode, options, catch_up, status,"
                " current_player_index, revision, evaluation_enabled, tracking_paused,"
                " win_confirmed, shadow_darts)"
                f" VALUES ('{variant}', {values}, 'active', 0, 0, false, false, false, '[]')"
                " RETURNING id"
            )[0][0]
        clock = ids["around_the_clock"]
        player = session.sql("INSERT INTO players (display_name) VALUES ('Ann') RETURNING id")[0][0]
        session.sql(
            "INSERT INTO game_players (game_id, player_index, player_id) VALUES (:game, 0, :player)",
            game=clock,
            player=player,
        )
        session.sql(
            "INSERT INTO game_turns (game_id, turn_index, player_index, busted)"
            " VALUES (:game, 0, 0, false)",
            game=clock,
        )
        for index, (value, multiplier) in enumerate([(1, 2), (2, 1)]):
            session.sql(
                "INSERT INTO game_darts (game_id, turn_index, dart_index, value, multiplier)"
                " VALUES (:game, 0, :index, :value, :multiplier)",
                game=clock,
                index=index,
                value=value,
                multiplier=multiplier,
            )
    finally:
        command.upgrade(config, "head")

    assert tuple(session.sql("SELECT start_score, checkout_mode, catch_up FROM game_x01")[0]) == (
        501,
        "single_out",
        True,
    )
    assert tuple(session.sql("SELECT start_score, kill FROM game_elimination")[0]) == (301, "any")
    assert session.sql("SELECT scoring FROM game_cricket")[0][0] == "no_score"
    assert tuple(session.sql("SELECT numbers, lives, zone FROM game_killer")[0]) == ([7, 12], 5, "any")
    assert tuple(session.sql("SELECT zone, skip FROM game_around_the_clock")[0]) == ("double", False)
    assert tuple(session.sql("SELECT goal, fields, repeats, seed FROM game_training")[0]) == (
        "fields",
        [[19, 3]],
        1,
        7,
    )
    targets = session.sql(
        "SELECT target_value, target_multiplier FROM game_darts ORDER BY dart_index"
    )
    assert [tuple(row) for row in targets] == [(1, 2), (2, 2)]
