from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional, Iterable

from board import Board
from config import AGENT_STEP_INTERVAL
from game_types import ActorType, BlockColor, Direction, Position, DOWN, LEFT, RIGHT, UP


@dataclass
class Agent:
    move_count: int = 0
    _cooldown: float = 0.0
    allow_green_nudge: bool = True

    def next_move(self, board: Board, dt: float) -> Optional[tuple[Position, Direction]]:
        self._cooldown += dt
        if self._cooldown < AGENT_STEP_INTERVAL:
            return None
        self._cooldown = 0.0
        move = self._plan_move(board)
        return move

    def _plan_move(self, board: Board) -> Optional[tuple[Position, Direction]]:
        assignments = self._assign_goals(board)
        if not assignments:
            return None
        reds = [pos for pos, block in board.iter_blocks() if block.color == BlockColor.RED]
        for red_pos in reds:
            goal = assignments.get(red_pos)
            if goal is None or red_pos == goal:
                continue
            # Try clear path (no blocks in the way)
            path_clear = self._bfs_path(board, red_pos, goal, allow_pass_through=())
            if len(path_clear) >= 2:
                return red_pos, self._direction_from_step(red_pos, path_clear[1])
            # Optional helper behavior to unblock reds by nudging greens.
            if self.allow_green_nudge:
                path_with_green = self._bfs_path(board, red_pos, goal, allow_pass_through={BlockColor.GREEN})
                if len(path_with_green) >= 2:
                    blocking_green = self._first_green_on_path(path_with_green, board)
                    if blocking_green:
                        move = self._nudge_green(blocking_green, board, avoid_positions=set(path_with_green))
                        if move:
                            return move
        return None

    def _assign_goals(self, board: Board) -> Optional[dict[Position, Position]]:
        red_positions = [pos for pos, block in board.iter_blocks() if block.color == BlockColor.RED]
        goals = list(board.goals)
        if len(red_positions) != len(goals):
            return None
        distances: dict[tuple[Position, Position], Optional[int]] = {}
        for r in red_positions:
            for g in goals:
                path = self._bfs_avoid_black(board, r, g)
                distances[(r, g)] = len(path) - 1 if path else None

        best_assignment: Optional[dict[Position, Position]] = None
        best_score = float("inf")

        def backtrack(idx: int, used: set[Position], current: dict[Position, Position], score: int) -> None:
            nonlocal best_assignment, best_score
            if idx == len(red_positions):
                if score < best_score:
                    best_score = score
                    best_assignment = current.copy()
                return
            red = red_positions[idx]
            for goal in goals:
                if goal in used:
                    continue
                dist = distances.get((red, goal))
                if dist is None:
                    continue
                if score + dist >= best_score:
                    continue
                current[red] = goal
                used.add(goal)
                backtrack(idx + 1, used, current, score + dist)
                used.remove(goal)
                current.pop(red, None)

        backtrack(0, set(), {}, 0)
        return best_assignment

    def _bfs_avoid_black(self, board: Board, start: Position, goal: Position) -> list[Position]:
        occupied = {pos for pos, block in board.iter_blocks() if block.color == BlockColor.BLACK}
        return self._bfs_generic(board, start, goal, occupied)

    def _bfs_path(self, board: Board, start: Position, goal: Position, allow_pass_through: Iterable[BlockColor]) -> list[Position]:
        allowed = set(allow_pass_through)
        occupied = {pos for pos, block in board.iter_blocks() if block.color not in allowed and pos != start}
        return self._bfs_generic(board, start, goal, occupied)

    def _bfs_generic(self, board: Board, start: Position, goal: Position, blocked: set[Position]) -> list[Position]:
        if start == goal:
            return [start]
        queue: deque[Position] = deque([start])
        came_from: dict[Position, Optional[Position]] = {start: None}
        directions = (UP, DOWN, LEFT, RIGHT)
        while queue:
            current = queue.popleft()
            if current == goal:
                break
            for direction in directions:
                nxt = (current[0] + direction.dx, current[1] + direction.dy)
                if not board.in_bounds(nxt) or nxt in blocked:
                    continue
                if nxt in came_from:
                    continue
                came_from[nxt] = current
                queue.append(nxt)
        if goal not in came_from:
            return []
        path = []
        node: Optional[Position] = goal
        while node is not None:
            path.append(node)
            node = came_from[node]
        path.reverse()
        return path

    def _direction_from_step(self, start: Position, nxt: Position) -> Direction:
        dx = nxt[0] - start[0]
        dy = nxt[1] - start[1]
        for d in (UP, DOWN, LEFT, RIGHT):
            if (d.dx, d.dy) == (dx, dy):
                return d
        return UP

    def _first_green_on_path(self, path: list[Position], board: Board) -> Optional[Position]:
        for pos in path[1:]:
            block = board.get_block(pos)
            if block and block.color == BlockColor.GREEN:
                return pos
        return None

    def _nudge_green(
        self,
        green_pos: Position,
        board: Board,
        avoid_positions: set[Position],
    ) -> Optional[tuple[Position, Direction]]:
        """Move a blocking green once to a free neighbor not on the red path."""
        for direction in (UP, DOWN, LEFT, RIGHT):
            target = (green_pos[0] + direction.dx, green_pos[1] + direction.dy)
            if not board.in_bounds(target):
                continue
            if target in board.blocks:
                continue
            if target in avoid_positions:
                continue
            return green_pos, direction
        return None
