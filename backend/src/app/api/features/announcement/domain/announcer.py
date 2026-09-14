"""Which device in a game's room speaks the booked darts (docs/feature/ansage.md §1)."""

from app.api.core.domain.client import Client
from app.api.core.domain.device_role import DeviceRole


def choose_announcer(
    present: list[Client], chosen_id: str | None, scoring_camera_id: str | None
) -> str | None:
    """The announcer among `present` (in join order): the chosen device, else the
    first scoreboard, else the scoring camera, else the first camera."""
    ids = [client.id for client in present]
    if chosen_id in ids:
        return chosen_id

    scoreboard = next((c.id for c in present if c.role is DeviceRole.SCOREBOARD), None)
    if scoreboard is not None:
        return scoreboard

    if scoring_camera_id in ids:
        return scoring_camera_id

    return ids[0] if ids else None
