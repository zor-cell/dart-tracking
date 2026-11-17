import pytest

D20 = {"value": 20, "multiplier": 2}
D16 = {"value": 16, "multiplier": 2}
D8 = {"value": 8, "multiplier": 2}
DOUBLES = {"variant": "personal", "focus": "doubles", "length": 45}


@pytest.fixture
def alice(register):
    return register("alice")


def plan(api, focus="doubles", length=45):
    response = api.get("/games/personal-plan")
    assert response.status_code == 200, response.text
    body = response.json()
    found = next(entry for entry in body["foci"] if entry["focus"] == focus)
    blocks = next(entry["blocks"] for entry in found["lengths"] if entry["length"] == length)
    return {"games": body["games"], "darts": body["darts"], "fields": found["fields"], "blocks": blocks}


def test_the_plan_and_the_training_need_an_account(anon):
    assert anon.get("/games/personal-plan").status_code == 401
    response = anon.post("/games", json={"players": [{"name": "Ann"}], "settings": DOUBLES})
    assert response.status_code == 401


def test_one_request_brings_the_plan_of_every_focus_and_length(alice):
    body = alice.get("/games/personal-plan").json()

    assert [entry["focus"] for entry in body["foci"]] == ["singles", "doubles", "triples", "all"]
    for entry in body["foci"]:
        assert [length["length"] for length in entry["lengths"]] == [45, 90, 150]
        for length in entry["lengths"]:
            assert sum(block["darts"] for block in length["blocks"]) == length["length"]


def test_without_darts_the_plan_probes_the_most_played_doubles(alice):
    body = plan(alice)
    assert (body["games"], body["darts"]) == (0, 0)
    assert [field["value"] for field in body["fields"]] == [20, 16, 8]
    assert not any(field["telling"] for field in body["fields"])
    assert [block["darts"] for block in body["blocks"]] == [12, 12, 12, 9]
    assert body["blocks"][-1]["fields"] == [D20, D16, D8]


def test_the_training_is_the_own_entry_alone(alice):
    guest = {"name": "Ben"}
    own = {"playerId": alice.own_entry()["id"]}

    for players in ([guest], [own, guest]):
        response = alice.post("/games", json={"players": players, "settings": DOUBLES})
        assert response.status_code == 422, response.text


def test_a_training_starts_on_the_plan_and_keeps_it(alice):
    game = alice.new_game(alice.own_entry()["id"], settings=DOUBLES)

    assert game["settings"] == {**DOUBLES, "anyRing": True, "minutes": None}
    standing = game["standing"]
    assert [block["fields"] for block in standing["blocks"]] == [[D20], [D16], [D8], [D20, D16, D8]]
    assert standing["baselines"] == [
        {**field, "darts": 0, "hits": 0, "located": 0, "distance": None} for field in (D20, D16, D8)
    ]
    player = standing["players"][0]
    assert (player["block"], player["target"], player["left"]) == (0, D20, 12)
    assert alice.get(f"/games/{game['id']}").json()["standing"] == standing


def test_a_finished_training_feeds_the_next_plan(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings=DOUBLES)["id"]
    hit, miss = [(20, 2)] * 3, [(0, 0)] * 3
    d16 = [(16, 2), (8, 2), (0, 0)]
    mixed = [(20, 2), (16, 1), (8, 1)]
    session.play(game_id, *[hit] * 4, *[d16] * 4, *[miss] * 4, *[mixed] * 3, hand_over=False)

    finished = alice.get(f"/games/{game_id}").json()
    assert finished["winnerId"] is not None
    player = finished["standing"]["players"][0]
    assert [(block["darts"], block["hits"]) for block in player["blocks"]] == [
        (12, 12), (12, 4), (12, 0), (9, 3)
    ]

    after = plan(alice)
    assert (after["games"], after["darts"]) == (1, 45)
    assert [field["value"] for field in after["fields"]] == [8, 16, 20]
    weakest = after["fields"][0]
    assert (weakest["darts"], weakest["hits"], weakest["telling"]) == (15, 0, True)
    assert (weakest["ringDarts"], weakest["ringHits"]) == (45, 19)


def test_the_switch_for_a_single_is_kept_only_where_the_focus_has_singles(alice):
    own = alice.own_entry()["id"]
    singles = alice.new_game(own, settings={**DOUBLES, "focus": "singles", "anyRing": False})
    doubles = alice.new_game(own, settings={**DOUBLES, "anyRing": False})

    assert alice.get(f"/games/{singles['id']}").json()["settings"]["anyRing"] is False
    assert doubles["settings"]["anyRing"] is True


def test_a_timed_training_shares_its_minutes_and_counts_down(alice, session):
    settings = {**DOUBLES, "minutes": 10}
    game = alice.new_game(alice.own_entry()["id"], settings=settings)

    assert game["settings"] == {**DOUBLES, "length": 90, "anyRing": True, "minutes": 10}
    assert [block["darts"] for block in game["standing"]["blocks"]] == [24, 24, 24, 18]
    assert game["standing"]["secondsLeft"] is None

    session.play(game["id"], [(20, 2)], hand_over=False)
    session.sql("UPDATE game_darts SET thrown_at = now() - interval '1 minute'")
    left = alice.get(f"/games/{game['id']}").json()["standing"]["secondsLeft"]
    assert 8 * 60 < left <= 9 * 60


def test_a_timed_training_takes_only_the_offered_minutes(alice):
    own = {"playerId": alice.own_entry()["id"]}
    response = alice.post("/games", json={"players": [own], "settings": {**DOUBLES, "minutes": 5}})
    assert response.status_code == 422


def test_a_timed_training_whose_time_ran_out_loads_as_ended(alice, session):
    game_id = alice.new_game(alice.own_entry()["id"], settings={**DOUBLES, "minutes": 10})["id"]
    session.play(game_id, [(16, 2), (16, 2), (16, 2)], hand_over=False)
    session.sql("UPDATE games SET status = 'finished' WHERE id = :id", id=game_id)

    loaded = alice.get(f"/games/{game_id}").json()

    assert loaded["ended"] is True
