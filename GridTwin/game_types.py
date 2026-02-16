from __future__ import annotations

from enum import Enum, auto
from typing import NamedTuple


class BlockColor(Enum):
    BLACK = "black"
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class ActorType(Enum):
    PLAYER = auto()
    AGENT = auto()


class Direction(NamedTuple):
    dx: int
    dy: int


UP = Direction(0, -1)
DOWN = Direction(0, 1)
LEFT = Direction(-1, 0)
RIGHT = Direction(1, 0)


Position = tuple[int, int]
