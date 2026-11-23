"""An in-memory frame store, so no test reaches a bucket."""


class MemoryFrameStore:
    def __init__(self) -> None:
        self.files: dict[tuple[str, str], bytes] = {}

    def write(self, game_id: str, name: str, data: bytes) -> None:
        self.files[game_id, name] = data

    def read(self, game_id: str, name: str) -> bytes | None:
        return self.files.get((game_id, name))

    def names(self, game_id: str) -> list[str]:
        return sorted(name for game, name in self.files if game == game_id)

    def remove(self, game_id: str, names: list[str]) -> None:
        for name in names:
            self.files.pop((game_id, name), None)

    def delete(self, game_id: str) -> None:
        self.remove(game_id, self.names(game_id))

    def games(self) -> list[str]:
        return sorted({game for game, _ in self.files})
