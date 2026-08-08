from dataclasses import dataclass


@dataclass(frozen=True)
class Dart:
    """One thrown dart: the field it landed in, which is what it scored.

    Storing the field rather than only its points keeps the called-out form
    ("T20") available for display — 60 alone cannot be told apart from 20 20 20.
    """

    value: int  # sector value, 25 for the bull, 0 for a miss
    multiplier: int  # 0 miss, 1 single, 2 double, 3 triple
    # Where the tip landed, in board millimetres, for a dart the camera located.
    # None for a manually entered one: there the field is known but the point
    # inside it is not. Carried on the game state so a device without a camera
    # can draw the throw on a board of its own.
    position: tuple[float, float] | None = None

    @property
    def points(self) -> int:
        return self.value * self.multiplier

    @property
    def label(self) -> str:
        """Short form as it is called out: 20, D20, T20, 25, 50, 0.

        Matches the vocabulary of the checkout suggestions (see checkout.py), so
        a thrown dart and a suggested one read alike side by side. Detection's
        `Segment.label` is a different, more explicit form (S20, BULL, MISS) used
        in the detection feedback.
        """
        if self.multiplier == 0:
            return "0"
        if self.value == 25:
            return "50" if self.multiplier == 2 else "25"
        return f"{('', 'D', 'T')[self.multiplier - 1]}{self.value}"
