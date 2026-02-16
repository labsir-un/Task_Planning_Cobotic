from __future__ import annotations

import sys
import time
import json
import threading
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import pygame
from pygame import Rect, Surface

from agent import Agent
from buildCif import build_cif, enumerate_instances
from board import Board
from config import (
    BACKGROUND_COLOR,
    FPS,
    GOAL_COLOR,
    GRID_COLOR,
    GRID_SIZE,
    HIGHLIGHT_COLOR,
    INFO_PANEL_HEIGHT,
    PADDING,
    TEXT_COLOR,
    WIN_TEXT_COLOR,
    TILE_SIZE,
)
from game_types import ActorType, BlockColor, Direction, Position, DOWN, LEFT, RIGHT, UP
from supervisor import SupervisorBridge

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

GRID_ROOT = Path(__file__).resolve().parent
PARENT = GRID_ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.append(str(PARENT))
from Main.ros_constants import (
    CIF_MOVE_COLORS,
    CIF_MOVE_DIRECTIONS,
    TOPIC_CIF_MOVE,
    TOPIC_CIF_MOVE_EVENT,
    TOPIC_CIF_START,
)


class GameState:
    SETUP = "setup"
    PLAYING = "playing"
    COMPLETE = "complete"


@dataclass
class Brush:
    color: Optional[BlockColor] = BlockColor.RED
    goal_mode: bool = False

    def label(self) -> str:
        if self.goal_mode:
            return "Goal marker"
        if self.color is None:
            return "Eraser"
        return f"{self.color.name.title()} block"


def color_to_rgb(color: BlockColor) -> tuple[int, int, int]:
    if color == BlockColor.BLACK:
        return (25, 25, 25)
    if color == BlockColor.RED:
        return (220, 60, 60)
    if color == BlockColor.BLUE:
        return (60, 120, 220)
    if color == BlockColor.GREEN:
        return (60, 170, 90)
    return (255, 255, 255)


def _direction_label(direction: Direction) -> str:
    if direction == UP:
        return "up"
    if direction == DOWN:
        return "down"
    if direction == LEFT:
        return "left"
    if direction == RIGHT:
        return "right"
    return "unknown"


class RosBridge:
    """ROS helper to publish state/events and accept setup/move commands while UI runs."""

    def __init__(self, game: "Game") -> None:
        self.game = game
        self.node: Optional[Node] = None
        self.executor: Optional[SingleThreadedExecutor] = None
        self.thread: Optional[threading.Thread] = None
        self.move_event_pub = None
        self.started = False

    @classmethod
    def start(cls, game: "Game") -> Optional["RosBridge"]:
        if rclpy is None:
            print("ROS not available; bridge disabled.")
            return None
        bridge = cls(game)
        try:
            rclpy.init(args=None)
            bridge.node = Node("cif_bridge_ui")
            bridge.move_event_pub = bridge.node.create_publisher(String, TOPIC_CIF_MOVE_EVENT, 10)
            bridge.node.create_subscription(String, TOPIC_CIF_MOVE, bridge._on_move_request, 10)
            bridge.node.create_subscription(String, TOPIC_CIF_START, bridge._on_start, 10)
            bridge.executor = SingleThreadedExecutor()
            bridge.executor.add_node(bridge.node)
            bridge.thread = threading.Thread(target=bridge.executor.spin, daemon=True)
            bridge.thread.start()
            return bridge
        except Exception as exc:
            print(f"Failed to start ROS bridge: {exc}")
            bridge.shutdown()
            return None

    def publish_move(self, start_pos: Position, direction: Direction, actor: ActorType) -> None:
        if self.move_event_pub is None or String is None:
            return
        target = (start_pos[0] + direction.dx, start_pos[1] + direction.dy)
        block = self.game.board.get_block(target)
        color = block.color.value if block else "unknown"
        name = _instance_name_at(target, self.game.instance_positions, self.game.board)
        number = _extract_number_from_name(name) if name else None
        payload = {
            "color": color,
            "id": number,
            "dir": _direction_label(direction),
            "actor": actor.name.lower(),
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.move_event_pub.publish(msg)

    def _on_setup(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._publish_event({"type": "setup_result", "success": False, "reason": "invalid_json"})
            return
        blocks = payload.get("blocks", [])
        goals = payload.get("goals", [])
        self.game.board.blocks.clear()
        self.game.board.goals.clear()
        for item in blocks:
            color = _blockcolor_from_str(str(item.get("color", "")))
            x = item.get("x")
            y = item.get("y")
            if color is None or x is None or y is None:
                continue
            self.game.board.place_block((int(x), int(y)), color)
        for g in goals:
            gx = g.get("x")
            gy = g.get("y")
            if gx is None or gy is None:
                continue
            self.game.board.goals.add((int(gx), int(gy)))

        instances = build_cif(self.game.board)
        self.game.instance_positions = {name: pos for name, _, pos in instances}
        if self.game.supervisor is not None:
            self.game.supervisor.shutdown()
        try:
            self.game.supervisor = SupervisorBridge.start(self.game.board, instances=instances)
        except Exception as exc:
            print(f"Failed to start supervisor from ROS setup: {exc}")
            self.game.supervisor = None
            self._publish_event({"type": "setup_result", "success": False, "reason": "supervisor_start_failed"})
            return

        self._publish_event({"type": "setup_result", "success": True})
        self._publish_state()

    def _on_move_request(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        dir_str = payload.get("dir")
        color_str = payload.get("color")
        number = payload.get("id")
        if dir_str is None or color_str is None or number is None:
            return
        direction = _direction_from_str(str(dir_str))
        color = _blockcolor_from_str(str(color_str))
        try:
            number_int = int(number)
        except Exception:
            number_int = None
        if direction is None or color is None or number_int is None:
            return
        name = _build_instance_name(color, number_int)
        start_pos = None
        if self.game.instance_positions:
            for inst, pos in self.game.instance_positions.items():
                if inst == name:
                    start_pos = pos
                    break
        if start_pos is None:
            return
        block = self.game.board.get_block(start_pos)
        if block is None or block.color != color:
            return
        ok = self.game._attempt_move(start_pos, direction, ActorType.PLAYER)
        if ok:
            self.publish_move(start_pos, direction, ActorType.PLAYER)

    def _on_start(self, msg: String) -> None:
        # Start the game using current board/supervisor; no payload needed.
        if self.started:
            return
        if self.game.supervisor is None:
            # If supervisor not running, attempt to build and start with current board.
            instances = build_cif(self.game.board)
            self.game.instance_positions = {name: pos for name, _, pos in instances}
            try:
                self.game.supervisor = SupervisorBridge.start(self.game.board, instances=instances)
            except Exception as exc:
                print(f"Failed to start supervisor from ROS start: {exc}")
                self.game.supervisor = None
                return
        self.game.state = GameState.PLAYING
        self.game.start_time = time.time()
        self.started = True

    def shutdown(self) -> None:
        try:
            if self.executor is not None:
                self.executor.shutdown()
            if self.node is not None:
                self.node.destroy_node()
        except Exception:
            pass
        try:
            if rclpy is not None:
                rclpy.shutdown()
        except Exception:
            pass


def _direction_from_str(value: str) -> Optional[Direction]:
    value = value.lower()
    if value == "up":
        return UP
    if value == "down":
        return DOWN
    if value == "left":
        return LEFT
    if value == "right":
        return RIGHT
    return None


def _actor_from_str(value: str) -> Optional[ActorType]:
    value = value.lower()
    if value == "player":
        return ActorType.PLAYER
    return None


def _blockcolor_from_str(value: str) -> Optional[BlockColor]:
    try:
        return BlockColor(value.lower())
    except Exception:
        return None


def _build_instance_name(color: BlockColor, number: int) -> str:
    return f"{color.value}{number}"


def _instance_name_at(
    pos: Position,
    instances: Optional[dict[str, Position]],
    board: Board,
) -> Optional[str]:
    if instances:
        for name, inst_pos in instances.items():
            if inst_pos == pos:
                return name
    for name, _, inst_pos in enumerate_instances(board):
        if inst_pos == pos:
            return name
    return None


def _extract_number_from_name(name: str) -> Optional[int]:
    digits = "".join(ch for ch in name if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except Exception:
        return None


class Game:
    def __init__(self) -> None:
        pygame.init()
        self.board = Board(GRID_SIZE, GRID_SIZE)
        self.agent = Agent()
        self.state: str = GameState.SETUP
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(
            (GRID_SIZE * TILE_SIZE, GRID_SIZE * TILE_SIZE + INFO_PANEL_HEIGHT)
        )
        pygame.display.set_caption("Custom Sokoban")
        self.font = pygame.font.SysFont("arial", 18)
        self.large_font = pygame.font.SysFont("arial", 24, bold=True)
        self.win_font = pygame.font.SysFont("arial", 48, bold=True)
        self.brush = Brush()
        self.selected: Optional[Position] = None
        self.player_move_count: int = 0
        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.supervisor: Optional[SupervisorBridge] = None
        self.instance_positions: Optional[dict[str, Position]] = None
        self.ros_bridge = RosBridge.start(self)

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            if self.state == GameState.PLAYING:
                self._update_agent(dt)
                if self.board.all_red_on_goals():
                    self.state = GameState.COMPLETE
                    if self.start_time is not None:
                        self.completion_time = time.time() - self.start_time
            self._render()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._shutdown_supervisor()
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse(event)

    def _handle_key(self, key: int) -> None:
        if self.state == GameState.SETUP:
            if key == pygame.K_r:
                self.brush = Brush(color=BlockColor.RED)
                print("Selected red brush (r)")
            elif key == pygame.K_g:
                self.brush = Brush(color=BlockColor.GREEN)
                print("Selected green brush (g)")
            elif key == pygame.K_b:
                self.brush = Brush(color=BlockColor.BLUE)
                print("Selected blue brush (b)")
            elif key == pygame.K_k:
                self.brush = Brush(color=BlockColor.BLACK)
                print("Selected black brush (k)")
            elif key == pygame.K_x:
                self.brush = Brush(goal_mode=True)
                print("Selected goal brush (x)")
            elif key == pygame.K_0:
                self.brush = Brush(color=None)
                print("Selected eraser (0)")
        elif self.state == GameState.PLAYING:
            # In play state, moves are handled via ROS only.
            if key == pygame.K_ESCAPE:
                self._shutdown_supervisor()
                pygame.quit()
                sys.exit()
        elif self.state == GameState.COMPLETE:
            if key == pygame.K_ESCAPE:
                self._shutdown_supervisor()
                pygame.quit()
                sys.exit()

    def _direction_from_key(self, key: int) -> Optional[Direction]:
        if key == pygame.K_UP:
            return UP
        if key == pygame.K_DOWN:
            return DOWN
        if key == pygame.K_LEFT:
            return LEFT
        if key == pygame.K_RIGHT:
            return RIGHT
        return None

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        mouse_pos = pygame.mouse.get_pos()
        grid_pos = self._mouse_to_grid(mouse_pos)
        if grid_pos is None:
            return
        if self.state == GameState.SETUP:
            if event.button == 1:  # left
                self._apply_brush(grid_pos)
            elif event.button == 3:  # right
                self.board.remove_block(grid_pos)
                if grid_pos in self.board.goals:
                    self.board.goals.remove(grid_pos)
        elif self.state == GameState.PLAYING:
            # User moves are handled via ROS; ignore clicks.
            return

    def _apply_brush(self, pos: Position) -> None:
        if self.brush.goal_mode:
            self.board.toggle_goal(pos)
            return
        if self.brush.color is None:
            self.board.remove_block(pos)
            return
        self.board.place_block(pos, self.brush.color)

    def _mouse_to_grid(self, pos: tuple[int, int]) -> Optional[Position]:
        x, y = pos
        if y >= GRID_SIZE * TILE_SIZE:
            return None
        return x // TILE_SIZE, y // TILE_SIZE

    def _attempt_move(self, pos: Position, direction: Direction, actor: ActorType) -> bool:
        if self.supervisor is not None:
            allowed = self.supervisor.request_move(pos, direction, actor)
            if not allowed:
                return False
        moved = self.board.move_block(pos, direction, actor)
        if moved and self.supervisor is not None:
            self.supervisor.update_position(pos, direction)
        if moved:
            self._update_instance_positions(pos, direction)
            if self.ros_bridge is not None:
                self.ros_bridge.publish_move(pos, direction, actor)
        return moved

    def _update_agent(self, dt: float) -> None:
        move = self.agent.next_move(self.board, dt)
        if move is None:
            return
        start, direction = move
        moved = self._attempt_move(start, direction, ActorType.AGENT)
        if moved:
            self.agent.move_count += 1

    def _shutdown_supervisor(self) -> None:
        if self.supervisor is not None:
            self.supervisor.shutdown()
        self.instance_positions = None
        if self.ros_bridge is not None:
            self.ros_bridge.shutdown()

    def _update_instance_positions(self, start_pos: Position, direction: Direction) -> None:
        if not self.instance_positions:
            return
        for name, pos in list(self.instance_positions.items()):
            if pos == start_pos:
                self.instance_positions[name] = (start_pos[0] + direction.dx, start_pos[1] + direction.dy)
                break

    def _instance_label_at(self, pos: Position) -> Optional[str]:
        if self.instance_positions:
            for name, inst_pos in self.instance_positions.items():
                if inst_pos == pos:
                    return self._extract_number(name)
        for name, _, inst_pos in enumerate_instances(self.board):
            if inst_pos == pos:
                return self._extract_number(name)
        return None

    def _extract_number(self, name: str) -> str:
        for i, ch in enumerate(name):
            if ch.isdigit():
                return name[i:]
        return name

    def _render(self) -> None:
        self.screen.fill(BACKGROUND_COLOR)
        self._draw_grid(self.screen)
        self._draw_goals(self.screen)
        self._draw_blocks(self.screen)
        self._draw_overlay(self.screen)
        pygame.display.flip()

    def _draw_grid(self, surface: Surface) -> None:
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                rect = Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(surface, GRID_COLOR, rect, width=1)

    def _draw_goals(self, surface: Surface) -> None:
        for gx, gy in self.board.goals:
            rect = Rect(gx * TILE_SIZE + PADDING, gy * TILE_SIZE + PADDING, TILE_SIZE - 2 * PADDING, TILE_SIZE - 2 * PADDING)
            pygame.draw.rect(surface, GOAL_COLOR, rect, width=2)

    def _draw_blocks(self, surface: Surface) -> None:
        for (bx, by), block in self.board.iter_blocks():
            rect = Rect(bx * TILE_SIZE + PADDING, by * TILE_SIZE + PADDING, TILE_SIZE - 2 * PADDING, TILE_SIZE - 2 * PADDING)
            pygame.draw.rect(surface, color_to_rgb(block.color), rect)
            if self.state == GameState.PLAYING and self.selected == (bx, by):
                pygame.draw.rect(surface, HIGHLIGHT_COLOR, rect, width=3)
            label = self._instance_label_at((bx, by))
            if label:
                text_image = self.font.render(label, True, TEXT_COLOR)
                text_rect = text_image.get_rect(center=rect.center)
                surface.blit(text_image, text_rect)

    def _draw_overlay(self, surface: Surface) -> None:
        panel_rect = Rect(0, GRID_SIZE * TILE_SIZE, GRID_SIZE * TILE_SIZE, INFO_PANEL_HEIGHT)
        pygame.draw.rect(surface, BACKGROUND_COLOR, panel_rect)
        if self.state == GameState.COMPLETE:
            self._draw_win_message(surface)
        stats = [
            f"Player moves: {self.player_move_count}",
            f"Agent moves: {self.agent.move_count}",
        ]
        if self.start_time and self.state == GameState.PLAYING:
            elapsed = time.time() - self.start_time
            stats.append(f"Time: {elapsed:0.1f}s")
        elif self.completion_time is not None:
            stats.append(f"Time: {self.completion_time:0.1f}s")
        for i, line in enumerate(stats):
            self._blit_text(surface, line, (12, GRID_SIZE * TILE_SIZE + 20 + i * 20), self.font)

    def _blit_text(self, surface: Surface, text: str, pos: tuple[int, int], font: pygame.font.Font) -> None:
        image = font.render(text, True, TEXT_COLOR)
        surface.blit(image, pos)

    def _draw_win_message(self, surface: Surface) -> None:
        message = "YOU WIN"
        text_image = self.win_font.render(message, True, WIN_TEXT_COLOR)
        text_rect = text_image.get_rect()
        text_rect.center = (GRID_SIZE * TILE_SIZE // 2, GRID_SIZE * TILE_SIZE // 2)
        surface.blit(text_image, text_rect)


if __name__ == "__main__":
    Game().run()
