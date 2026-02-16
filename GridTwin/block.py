from __future__ import annotations

from dataclasses import dataclass

from game_types import BlockColor


@dataclass(frozen=True)
class Block:
    color: BlockColor
