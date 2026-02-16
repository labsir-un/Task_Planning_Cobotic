from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Set

from block import Block
from game_types import ActorType, BlockColor, Direction, Position


def _allowed_colors(actor: ActorType) -> Set[BlockColor]:
    if actor == ActorType.PLAYER:
        return {BlockColor.BLUE, BlockColor.GREEN}
    return {BlockColor.RED, BlockColor.GREEN}


@dataclass
class Board:
    width: int
    height: int
    blocks: dict[Position, Block] = field(default_factory=dict)
    goals: set[Position] = field(default_factory=set)

    def in_bounds(self, pos: Position) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def get_block(self, pos: Position) -> Optional[Block]:
        return self.blocks.get(pos)

    def is_goal(self, pos: Position) -> bool:
        return pos in self.goals

    def toggle_goal(self, pos: Position) -> None:
        if pos in self.goals:
            self.goals.remove(pos)
        else:
            self.goals.add(pos)

    def place_block(self, pos: Position, color: BlockColor) -> None:
        if not self.in_bounds(pos):
            return
        self.blocks[pos] = Block(color)

    def remove_block(self, pos: Position) -> None:
        self.blocks.pop(pos, None)

    def move_block(self, pos: Position, direction: Direction, actor: ActorType) -> bool:
        block = self.blocks.get(pos)
        if block is None:
            return False
        if block.color not in _allowed_colors(actor):
            return False
        target = (pos[0] + direction.dx, pos[1] + direction.dy)
        if not self.in_bounds(target) or target in self.blocks:
            return False
        if block.color == BlockColor.BLACK:
            return False
        # Move
        self.blocks[target] = block
        del self.blocks[pos]
        return True

    def occupied_positions(self, exclude: Optional[Position] = None) -> Set[Position]:
        if exclude is None:
            return set(self.blocks.keys())
        return {pos for pos in self.blocks if pos != exclude}

    def all_red_on_goals(self) -> bool:
        for pos, block in self.blocks.items():
            if block.color == BlockColor.RED and pos not in self.goals:
                return False
        # No red blocks out of goals
        return True

    def iter_blocks(self) -> Iterable[tuple[Position, Block]]:
        return self.blocks.items()
