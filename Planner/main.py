from __future__ import annotations

import itertools
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import rclpy
from plansys2_msgs.srv import GetPlan
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from Orchestrator.ros_constants import TOPIC_PLANNER_IN, TOPIC_PLANNER_OUT, TOPIC_PLANNER_START

PLAN_SERVICE = "/planner/get_plan"
GRID_W = 10
GRID_H = 10
SEARCH_MARGIN = 1


class PlannerNode(Node):
    def __init__(self) -> None:
        super().__init__("planner_node")
        self.create_subscription(String, TOPIC_PLANNER_START, self._on_start, 10)
        self.create_subscription(String, TOPIC_PLANNER_IN, self._on_in, 10)
        self.out_pub = self.create_publisher(String, TOPIC_PLANNER_OUT, 10)
        self.plan_client = self.create_client(GetPlan, PLAN_SERVICE)

        self.domain_text = (Path(__file__).resolve().parent / "domain.pddl").read_text()
        self.started = False
        self.waiting_done = False
        self.phase = "setup"
        self.blocks: list[tuple[str, int, int, int]] = []
        self.goals: set[tuple[int, int]] = set()
        self.pending_plan_future = None
        self.plan_queue: list[str] = []
        self.needs_plan = True
        self.create_timer(0.1, self._check_plan_future)
        self.get_logger().info("Planner module started.")
        self._ensure_plansys2_running()

    def _report_plan_failure(self, reason: str) -> None:
        self.get_logger().warning(f"Planning failed: {reason}")
        self._publish_out("plan_failed")

    def _ensure_plansys2_running(self) -> None:
        domain_file = str((Path(__file__).resolve().parent / "domain.pddl"))
        launch_cmd = (
            "ros2 launch plansys2_bringup plansys2_bringup_launch_monolithic.py "
            f"model_file:={domain_file}"
        )
        self.get_logger().info("PROCESS launching PlanSys2 in a new terminal.")
        try:
            subprocess.Popen(
                ["gnome-terminal", "--", "bash", "-lc", f"{launch_cmd}; exec bash"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=os.environ.copy(),
            )
            self.get_logger().info(f"Started PlanSys2 terminal with: {launch_cmd}")
        except FileNotFoundError:
            self.get_logger().error("gnome-terminal not found. Start PlanSys2 manually.")
        except Exception as exc:
            self.get_logger().error(f"Failed to launch PlanSys2 terminal: {exc}")

    def _on_start(self, _: String) -> None:
        self.started = True
        self.waiting_done = False
        self.needs_plan = True
        self.plan_queue = []
        self.get_logger().info("Planner started.")
        self._publish_out("request_state")

    def _on_in(self, msg: String) -> None:
        text = msg.data.strip().lower()
        if not text:
            return
        self.get_logger().info(f"planner/in: {text}")

        if text == "replan":
            self.get_logger().info("PROCESS replan requested.")
            self.waiting_done = False
            self.needs_plan = True
            self.plan_queue = []
            self._publish_out("request_state")
            return

        if text == "done":
            self.get_logger().info("PROCESS action done received, dispatching next planned action.")
            self.waiting_done = False
            self._dispatch_next_action()
            return

        if text.startswith("state "):
            self._parse_state(text)
            if self.started and self._all_red_on_goals():
                self.plan_queue = []
                self.needs_plan = False
                self._publish_out("complete")
                return
            if self.started and not self.waiting_done and self.phase == "playing" and self.needs_plan:
                self._plan_and_publish()

    def _all_red_on_goals(self) -> bool:
        reds = [(x, y) for color, _, x, y in self.blocks if color == "red"]
        return bool(reds) and all(pos in self.goals for pos in reds)

    def _parse_state(self, text: str) -> None:
        # Format: state <phase> blocks <c:id:x:y;...> goals <x:y;...>
        try:
            _, rest = text.split(" ", 1)
            phase, rest = rest.split(" blocks ", 1)
            blocks_part, goals_part = rest.split(" goals ", 1)
        except ValueError:
            self.get_logger().warning("Invalid state format.")
            return

        parsed_blocks: list[tuple[str, int, int, int]] = []
        if blocks_part and blocks_part != "-":
            for token in blocks_part.split(";"):
                try:
                    color, sid, sx, sy = token.split(":")
                    parsed_blocks.append((color, int(sid), int(sx), int(sy)))
                except ValueError:
                    continue

        parsed_goals: set[tuple[int, int]] = set()
        if goals_part and goals_part != "-":
            for token in goals_part.split(";"):
                try:
                    sx, sy = token.split(":")
                    parsed_goals.add((int(sx), int(sy)))
                except ValueError:
                    continue

        self.phase = phase
        self.blocks = parsed_blocks
        self.goals = parsed_goals

    def _plan_and_publish(self) -> None:
        if self.pending_plan_future is not None:
            self.get_logger().info("PROCESS plan request already in-flight, waiting result.")
            return
        self.get_logger().info("PROCESS building PDDL problem and requesting plan.")
        reds = [(bid, x, y) for color, bid, x, y in self.blocks if color == "red"]
        if not reds:
            self._publish_out("complete")
            return
        if all((x, y) in self.goals for _, x, y in reds):
            self._publish_out("complete")
            return

        goal_map = self._assign_goals(reds, self.goals)
        if goal_map is None:
            self._report_plan_failure("no goal assignment available for red blocks")
            return

        self.get_logger().info("PROCESS full-goal planning for all red blocks.")
        problem_text = self._build_problem_text(goal_map)
        self._publish_out("planning")
        if not self._request_plan(problem_text):
            self._report_plan_failure("no plan request sent to PlanSys2")
            return

    def _assign_goals(
        self,
        reds: list[tuple[int, int, int]],
        goals: set[tuple[int, int]],
    ) -> Optional[dict[str, tuple[int, int]]]:
        if len(goals) < len(reds):
            return None
        goal_list = list(goals)
        best_score = None
        best_assignment: Optional[dict[str, tuple[int, int]]] = None
        red_names = [f"red{bid}" for bid, _, _ in reds]
        red_pos = {f"red{bid}": (x, y) for bid, x, y in reds}

        for combo in itertools.permutations(goal_list, len(reds)):
            score = 0
            tmp: dict[str, tuple[int, int]] = {}
            for idx, red_name in enumerate(red_names):
                g = combo[idx]
                sx, sy = red_pos[red_name]
                score += abs(sx - g[0]) + abs(sy - g[1])
                tmp[red_name] = g
            if best_score is None or score < best_score:
                best_score = score
                best_assignment = tmp
        return best_assignment

    def _cell(self, x: int, y: int) -> str:
        return f"c_{x}_{y}"

    def _all_cells(self) -> list[tuple[int, int]]:
        return [(x, y) for x in range(GRID_W) for y in range(GRID_H)]

    def _expand_with_margin(self, seeds: set[tuple[int, int]], margin: int) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for sx, sy in seeds:
            for dx in range(-margin, margin + 1):
                for dy in range(-margin, margin + 1):
                    x = sx + dx
                    y = sy + dy
                    if 0 <= x < GRID_W and 0 <= y < GRID_H:
                        cells.add((x, y))
        return cells

    def _build_relevant_cells(self, goal_map: dict[str, tuple[int, int]]) -> set[tuple[int, int]]:
        seeds: set[tuple[int, int]] = set()
        for color, _, x, y in self.blocks:
            if color != "black":
                seeds.add((x, y))
        for gx, gy in goal_map.values():
            seeds.add((gx, gy))
        if not seeds:
            return set(self._all_cells())
        cells = self._expand_with_margin(seeds, SEARCH_MARGIN)
        # Always include direct Manhattan corridors from each red to its assigned goal.
        red_positions = {f"red{bid}": (x, y) for color, bid, x, y in self.blocks if color == "red"}
        for red_symbol, (gx, gy) in goal_map.items():
            if red_symbol not in red_positions:
                continue
            x, y = red_positions[red_symbol]
            step_x = 1 if gx >= x else -1
            while x != gx:
                cells.add((x, y))
                x += step_x
                cells.add((x, y))
            step_y = 1 if gy >= y else -1
            while y != gy:
                cells.add((x, y))
                y += step_y
                cells.add((x, y))
        return cells

    def _adjacent_facts(self) -> list[str]:
        facts: list[str] = []
        for x, y in self._all_cells():
            c = self._cell(x, y)
            for nx, ny, d in (
                (x, y - 1, "up"),
                (x, y + 1, "down"),
                (x - 1, y, "left"),
                (x + 1, y, "right"),
            ):
                if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                    facts.append(f"(adjacent {c} {self._cell(nx, ny)} {d})")
        return facts

    def _adjacent_facts_for(self, cells: set[tuple[int, int]]) -> list[str]:
        facts: list[str] = []
        for x, y in sorted(cells):
            c = self._cell(x, y)
            for nx, ny, d in (
                (x, y - 1, "up"),
                (x, y + 1, "down"),
                (x - 1, y, "left"),
                (x + 1, y, "right"),
            ):
                if (nx, ny) in cells:
                    facts.append(f"(adjacent {c} {self._cell(nx, ny)} {d})")
        return facts

    def _build_problem_text(self, goal_map: dict[str, tuple[int, int]]) -> str:
        relevant_cells = self._build_relevant_cells(goal_map)
        occupied = {(x, y) for _, _, x, y in self.blocks if (x, y) in relevant_cells}
        red_objs: list[str] = []
        blue_objs: list[str] = []
        green_objs: list[str] = []
        init_facts: list[str] = []

        for color, sid, x, y in self.blocks:
            if color == "black":
                continue
            if (x, y) not in relevant_cells:
                continue
            symbol = f"{color}{sid}"
            if color == "red":
                red_objs.append(symbol)
            elif color == "blue":
                blue_objs.append(symbol)
            elif color == "green":
                green_objs.append(symbol)
            else:
                continue
            init_facts.append(f"(at {symbol} {self._cell(x, y)})")

        for x, y in sorted(relevant_cells):
            if (x, y) not in occupied:
                init_facts.append(f"(free {self._cell(x, y)})")

        init_facts.extend(self._adjacent_facts_for(relevant_cells))
        for red_symbol, (gx, gy) in goal_map.items():
            init_facts.append(f"(goal {red_symbol} {self._cell(gx, gy)})")

        all_cells = " ".join(self._cell(x, y) for x, y in sorted(relevant_cells))
        dirs = "up down left right"
        goal_expr = " ".join(
            f"(at {red_symbol} {self._cell(gx, gy)})"
            for red_symbol, (gx, gy) in goal_map.items()
        )
        self.get_logger().info(
            f"PROCESS reduced planning cells: {len(relevant_cells)}/{GRID_W * GRID_H}"
        )

        lines = [
            "(define (problem cobot_instance)",
            "  (:domain cobot_grid)",
            "  (:objects",
            f"    {all_cells} - cell",
            f"    {dirs} - dir",
        ]
        if red_objs:
            lines.append(f"    {' '.join(red_objs)} - red")
        if blue_objs:
            lines.append(f"    {' '.join(blue_objs)} - blue")
        if green_objs:
            lines.append(f"    {' '.join(green_objs)} - green")
        lines.extend(
            [
                "  )",
                "  (:init",
            ]
        )
        for fact in init_facts:
            lines.append(f"    {fact}")
        lines.extend(
            [
                "  )",
                f"  (:goal (and {goal_expr}))",
                ")",
            ]
        )
        return "\n".join(lines)

    def _request_plan(self, problem_text: str) -> bool:
        if not self.plan_client.wait_for_service(timeout_sec=0.5):
            self.get_logger().warning("PlanSys2 service /planner/get_plan not available.")
            return False
        self.get_logger().info("PROCESS calling /planner/get_plan.")
        req = GetPlan.Request()
        req.domain = self.domain_text
        req.problem = problem_text
        self.pending_plan_future = self.plan_client.call_async(req)
        return True

    def _check_plan_future(self) -> None:
        future = self.pending_plan_future
        if future is None:
            return
        if not future.done():
            return

        self.pending_plan_future = None
        resp = future.result()
        if resp is None:
            self._report_plan_failure("PlanSys2 returned no result object")
            return
        if not resp.success:
            self._report_plan_failure(f"PlanSys2 returned success=false: {resp.error_info}")
            return
        self.get_logger().info(f"PROCESS planner returned {len(resp.plan.items)} action(s).")
        self.plan_queue = [item.action for item in resp.plan.items]
        self.needs_plan = False
        if not self.plan_queue:
            self._report_plan_failure("empty plan returned by PlanSys2")
            return
        self._dispatch_next_action()

    def _dispatch_next_action(self) -> None:
        while self.plan_queue:
            raw = self.plan_queue.pop(0)
            action = self._parse_action(raw)
            if action is None:
                self._report_plan_failure(f"could not parse plan action: {raw}")
                return
            out = self._map_action_to_output(action)
            if out is None:
                self._report_plan_failure(f"unsupported action from plan: {action[0]}")
                return
            self.waiting_done = True
            self._publish_out(out)
            return

        self.get_logger().info("PROCESS plan queue exhausted, requesting state verification.")
        self.waiting_done = False
        self._publish_out("request_state")

    def _parse_action(self, raw: str) -> Optional[tuple[str, list[str]]]:
        # Handles "(action ...)" and "0: (action ...)" forms.
        start = raw.find("(")
        end = raw.rfind(")")
        if start < 0 or end <= start:
            return None
        content = raw[start + 1 : end].strip()
        tokens = content.split()
        if not tokens:
            return None
        return tokens[0], tokens[1:]

    def _map_action_to_output(self, action: tuple[str, list[str]]) -> Optional[str]:
        name, args = action
        if len(args) != 4:
            return None
        block_name, _, _, direction = args
        if not direction in {"up", "down", "left", "right"}:
            return None
        parsed = self._parse_block_name(block_name)
        if parsed is None:
            return None
        color, sid = parsed
        if name == "user_move_blue" and color == "blue":
            return f"user blue {sid} {direction}"
        if name == "user_move_green" and color == "green":
            return f"user green {sid} {direction}"
        if name == "robot_move_green" and color == "green":
            return f"robot green {sid} {direction}"
        if name == "robot_move_red" and color == "red":
            return f"robot red {sid} {direction}"
        return None

    def _parse_block_name(self, symbol: str) -> Optional[tuple[str, int]]:
        for color in ("red", "blue", "green"):
            if symbol.startswith(color):
                suffix = symbol[len(color) :]
                if suffix.isdigit():
                    return color, int(suffix)
        return None

    def _publish_out(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.out_pub.publish(msg)
        self.get_logger().info(f"planner/out: {text}")


def main() -> None:
    rclpy.init()
    node = PlannerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
