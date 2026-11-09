from app.api.core.domain.language import Language
from app.api.features.announcement.services.speech import clip_id, clip_url
from tests.api.test_socket import Device, game_id, room  # noqa: F401


def test_the_announcer_hears_clips_in_its_own_language(client, room, game_id, voiced):
    url = f"/api/ws/games/{game_id}"
    with client.websocket_connect(url, headers={"cookie": "lang=de"}) as websocket:
        announcer = Device(websocket)
        with room(game_id) as other:
            for _ in range(3):
                other.throw(20, 3)
            announcements = [announcer.next("dart_announcement") for _ in range(3)]

    assert announcements[-1]["clips"] == [
        clip_url(clip_id(text, Language.DE)) for text in ("Trippel 20", "180")
    ]
    assert "Triple 20" not in voiced


def test_a_clip_is_served_once_voiced(client, room, game_id):
    with room(game_id) as device:
        device.throw(25, 2)
        clips = device.next("dart_announcement")["clips"]

    response = client.get(clips[0])

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert "immutable" in response.headers["cache-control"]


def test_an_unknown_clip_is_not_found(client):
    assert client.get(clip_url("0" * 32)).status_code == 404


def test_the_sound_test_speaks_the_requests_language(client, voiced):
    response = client.get("/api/announcer/test", headers={"cookie": "lang=de"})

    assert response.json()["clips"] == [clip_url(clip_id("Los geht's", Language.DE))]
    assert voiced == ["Los geht's"]
