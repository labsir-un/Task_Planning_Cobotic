from __future__ import annotations

from pathlib import Path
from typing import Iterable

from board import Board
from game_types import BlockColor, Position


def _to_cif_coords(pos: Position, height: int) -> Position:
    x, y = pos
    return (x, height - 1 - y)


def enumerate_instances(board: Board) -> list[tuple[str, BlockColor, Position]]:
    """Assign deterministic instance names to all blocks on the board (based on CIF coords)."""
    instances: list[tuple[str, BlockColor, Position]] = []
    for color in (BlockColor.RED, BlockColor.BLUE, BlockColor.GREEN, BlockColor.BLACK):
        positions = _sorted_positions((pos for pos, block in board.iter_blocks() if block.color == color), board.height)
        for idx, pos in enumerate(positions, start=1):
            instances.append((f"{color.value}{idx}", color, pos))
    return instances


def build_cif(board: Board, goals_path: str | Path = "goals.cif", sokoban_path: str | Path = "sokoban.cif") -> list[tuple[str, BlockColor, Position]]:
    """Generate CIF files for the current board layout and return instances."""
    instances = enumerate_instances(board)
    _write_goals(board.goals, board.height, goals_path)
    _write_sokoban(instances, board.height, sokoban_path)
    return instances


def _sorted_positions(items: Iterable[Position], height: int) -> list[Position]:
    return sorted(items, key=lambda p: (p[0], _to_cif_coords(p, height)[1]))


def _write_goals(goals: set[Position], height: int, path: str | Path) -> None:
    path = Path(path)
    sorted_goals = _sorted_positions(goals, height)
    lines: list[str] = []
    lines.append("const set tuple(int x,y) goals = {")
    for i, pos in enumerate(sorted_goals):
        gx, gy = _to_cif_coords(pos, height)
        suffix = "," if i < len(sorted_goals) - 1 else ""
        lines.append(f"    ({gx},{gy}){suffix}")
    lines.append("};")
    lines.append("")
    lines.append("func bool inGoal(int x,y):")
    lines.append("    return (x,y) in goals;")
    lines.append("end")
    lines.append("")
    path.write_text("\n".join(lines))


def _write_sokoban(instances: list[tuple[str, BlockColor, Position]], height: int, path: str | Path) -> None:
    path = Path(path)
    lines: list[str] = []
    lines.append('import "block.cif";')
    lines.append("")
    for name, color, pos in instances:
        cx, cy = _to_cif_coords(pos, height)
        lines.append(f"{name}: {color.value}({cx},{cy});")
    lines.append("")
    lines.extend(_collision_requirement(instances))
    path.write_text("\n".join(lines))


def _collision_requirement(instances: list[tuple[str, BlockColor, Position]]) -> list[str]:
    count = len(instances)
    lines: list[str] = []
    lines.append("requirement avoidCollision:")
    lines.append("    alg set tuple(int x,y) occupied = {")
    for i, (name, _, _) in enumerate(instances):
        suffix = "," if i < len(instances) - 1 else ""
        lines.append(f"        ({name}.x, {name}.y){suffix}")
    lines.append("    };")
    lines.append("")
    lines.append("    location:")
    lines.append("        initial;")
    lines.append(f"        requirement invariant size(occupied) = {count};")
    lines.append("end")
    lines.append("")
    return lines
