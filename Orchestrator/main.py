from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from Orchestrator.ros_constants import (
    DIRECTIONS,
    PLAYER_COLORS,
    ROBOT_COLORS,
    TOPIC_ABB_IN,
    TOPIC_ABB_OUT,
    TOPIC_GRIDTWIN_IN,
    TOPIC_GRIDTWIN_OUT,
    TOPIC_GRIDTWIN_START,
    TOPIC_NLP_IN,
    TOPIC_NLP_OUT,
    TOPIC_PLANNER_IN,
    TOPIC_PLANNER_OUT,
    TOPIC_PLANNER_START,
)


class Orchestrator(Node):
    def __init__(self) -> None:
        super().__init__("orchestrator")
        self.create_subscription(String, TOPIC_NLP_OUT, self._on_nlp_out, 10)
        self.create_subscription(String, TOPIC_PLANNER_OUT, self._on_planner_out, 10)
        self.create_subscription(String, TOPIC_GRIDTWIN_OUT, self._on_gridtwin_out, 10)
        self.create_subscription(String, TOPIC_ABB_OUT, self._on_abb_out, 10)

        self.nlp_in_pub = self.create_publisher(String, TOPIC_NLP_IN, 10)
        self.planner_start_pub = self.create_publisher(String, TOPIC_PLANNER_START, 10)
        self.planner_in_pub = self.create_publisher(String, TOPIC_PLANNER_IN, 10)
        self.gridtwin_start_pub = self.create_publisher(String, TOPIC_GRIDTWIN_START, 10)
        self.gridtwin_in_pub = self.create_publisher(String, TOPIC_GRIDTWIN_IN, 10)
        self.abb_in_pub = self.create_publisher(String, TOPIC_ABB_IN, 10)

        self.started = False
        self.mode = "idle"
        self.pending_actor: Optional[str] = None
        self.pending_color: Optional[str] = None
        self.pending_id: Optional[int] = None
        self.pending_dir: Optional[str] = None
        self.pending_x: Optional[int] = None
        self.pending_y: Optional[int] = None
        self.last_positions: dict[tuple[str, int], tuple[int, int]] = {}
        self.pending_user_prompt: Optional[str] = None
        self.get_logger().info("Orchestrator module started.")

    def _on_nlp_out(self, msg: String) -> None:
        text = msg.data.strip().lower()
        self.get_logger().info(f"READ /nlp/out: {text}")

        if self.mode == "halted":
            return

        if self.mode == "await_fixed":
            if text == "fixed":
                self.get_logger().info("PROCESS received fixed, restarting plan cycle.")
                self._publish(self.nlp_in_pub, "Resuming. Re-planning now.", "/nlp/in")
                self.mode = "running"
                self._clear_pending()
                self._publish(self.planner_in_pub, "replan", "/planner/in")
                self._publish(self.gridtwin_in_pub, "state", "/gridtwin/in")
            return

        if not self.started:
            if text == "start":
                self.started = True
                self.mode = "running"
                self.get_logger().info("PROCESS start received, starting GridTwin and Planner.")
                self._publish(self.gridtwin_start_pub, "start", "/gridtwin/start")
                self._publish(self.planner_start_pub, "start", "/planner/start")
            return

        if self.mode == "waiting_user_direction":
            if text == "space":
                self.get_logger().info("PROCESS user requested space, sending special ABB command.")
                self.mode = "waiting_space_abb_result"
                self._publish(self.abb_in_pub, "XXXXX", "/abb/in")
                return
            if text == "done":
                if not self._has_pending():
                    self._fail("Missing pending user action.")
                    return
                if self.pending_dir is None:
                    self._fail("Missing pending user move direction.")
                    return
                move_cmd = f"move player {self.pending_color} {self.pending_id} {self.pending_dir}"
                self.mode = "waiting_user_move_result"
                self.get_logger().info(f"PROCESS forwarding user move to GridTwin: {move_cmd}")
                self._publish(self.gridtwin_in_pub, move_cmd, "/gridtwin/in")
            return

        if self.mode == "waiting_robot_continue":
            if text == "go":
                if not self._has_pending():
                    self._fail("Missing pending robot action.")
                    return
                if self.pending_dir is None:
                    self._fail("Missing pending robot direction.")
                    return
                pos = self.last_positions.get((self.pending_color, self.pending_id))
                if pos is None:
                    self._fail("Missing block position from latest GridTwin state.")
                    return
                self.pending_x, self.pending_y = pos
                self.mode = "waiting_abb_result"
                self.get_logger().info("PROCESS forwarding planned robot move to ABB.")
                self._publish(self.abb_in_pub, f"move {pos[0]} {pos[1]} {self.pending_dir}", "/abb/in")
            return

    def _on_planner_out(self, msg: String) -> None:
        text = msg.data.strip().lower()
        self.get_logger().info(f"READ /planner/out: {text}")
        if not self.started or self.mode == "await_fixed":
            return

        if text == "request_state":
            self.get_logger().info("PROCESS planner requested state.")
            self._publish(self.gridtwin_in_pub, "state", "/gridtwin/in")
            return
        if text == "planning":
            self._publish(self.nlp_in_pub, "Planning in progress, please wait.", "/nlp/in")
            return
        if text == "plan_failed":
            self.get_logger().warning("PROCESS planner reported plan failure, halting flow.")
            self.mode = "halted"
            self._clear_pending()
            self._publish(
                self.nlp_in_pub,
                "Unable to find a plan to reach the goal, please check state of the system and restart.",
                "/nlp/in",
            )
            return

        if text == "complete":
            self._publish(self.nlp_in_pub, "All goals achieved. You win.", "/nlp/in")
            return

        parts = text.split()
        if len(parts) != 4:
            self._fail(f"Invalid planner action: {text}")
            return
        actor, color, sid, direction = parts
        if direction not in DIRECTIONS:
            self._fail(f"Invalid planner direction: {direction}")
            return
        try:
            block_id = int(sid)
        except ValueError:
            self._fail(f"Invalid planner block id: {sid}")
            return

        if actor == "user":
            if color not in PLAYER_COLORS:
                self._fail(f"Invalid user color from planner: {color}")
                return
            self._set_pending(actor, color, block_id, direction)
            self.mode = "waiting_user_direction"
            self.pending_user_prompt = (
                f"Please move {color} block number {block_id} {direction}, then confirm by saying done."
            )
            self._publish(
                self.nlp_in_pub,
                self.pending_user_prompt,
                "/nlp/in",
            )
            return

        if actor == "robot":
            if color not in ROBOT_COLORS:
                self._fail(f"Invalid robot color from planner: {color}")
                return
            self._set_pending(actor, color, block_id, direction)
            self.mode = "waiting_robot_continue"
            self.pending_user_prompt = None
            self._publish(
                self.nlp_in_pub,
                f"Robot will move {color} block number {block_id} {direction}. Say go when ready.",
                "/nlp/in",
            )
            return

        self._fail(f"Unknown planner actor: {actor}")

    def _on_gridtwin_out(self, msg: String) -> None:
        text = msg.data.strip()
        lowered = text.lower()
        self.get_logger().info(f"READ /gridtwin/out: {text}")

        if lowered.startswith("state "):
            self.get_logger().info("PROCESS caching GridTwin state and forwarding to Planner.")
            self._update_state_cache(lowered)
            self._publish(self.planner_in_pub, lowered, "/planner/in")
            return

        if lowered.startswith("error ") or lowered.startswith("move_fail "):
            self._fail(f"GridTwin reported failure: {text}")
            return

        parts = lowered.split()
        if not parts:
            return

        if parts[0] == "move_ok" and len(parts) == 7:
            _, actor, color, sid, direction, sx, sy = parts
            self._update_position_cache_on_move_ok(color, sid, sx, sy)
            if self.mode == "waiting_user_move_result":
                if not self._pending_matches("user", color, sid):
                    self._fail("User move ack mismatch from GridTwin.")
                    return
                if direction not in DIRECTIONS:
                    self._fail("Invalid user direction in GridTwin move_ok.")
                    return
                if self.pending_dir is not None and direction != self.pending_dir:
                    self._fail("User move direction does not match planner command.")
                    return
                self.mode = "running"
                self._clear_pending()
                self._publish(self.planner_in_pub, "done", "/planner/in")
                return
            if self.mode == "waiting_robot_apply":
                if not self._pending_matches("robot", color, sid):
                    self._fail("Robot move apply ack mismatch from GridTwin.")
                    return
                if direction not in DIRECTIONS:
                    self._fail("Invalid robot direction in GridTwin move_ok.")
                    return
                self.mode = "running"
                self._clear_pending()
                self._publish(self.planner_in_pub, "done", "/planner/in")
                return

    def _update_position_cache_on_move_ok(self, color: str, sid: str, sx: str, sy: str) -> None:
        try:
            block_id = int(sid)
            x = int(sx)
            y = int(sy)
        except ValueError:
            return
        self.last_positions[(color, block_id)] = (x, y)

    def _on_abb_out(self, msg: String) -> None:
        text = msg.data.strip().lower()
        self.get_logger().info(f"READ /abb/out: {text}")
        if self.mode == "waiting_space_abb_result":
            if text == "ok":
                self.get_logger().info("PROCESS ABB space command succeeded, repeating user instruction.")
                self.mode = "waiting_user_direction"
                if self.pending_user_prompt:
                    self._publish(self.nlp_in_pub, self.pending_user_prompt, "/nlp/in")
                return
            self._fail("ABB reported fail on space command.")
            return
        if self.mode != "waiting_abb_result":
            return
        if text == "ok":
            if not self._has_pending() or self.pending_dir is None:
                self._fail("Missing pending robot state after ABB ok.")
                return
            self.mode = "waiting_robot_apply"
            self.get_logger().info("PROCESS ABB robot move succeeded, applying move to GridTwin.")
            self._publish(
                self.gridtwin_in_pub,
                f"move agent {self.pending_color} {self.pending_id} {self.pending_dir}",
                "/gridtwin/in",
            )
            self._publish(self.nlp_in_pub, "Robot movement successful, please validate results.", "/nlp/in")
            return
        if text == "fail":
            self._fail("ABB reported fail.")
            return
        self._fail(f"Unknown ABB response: {text}")

    def _set_pending(self, actor: str, color: str, block_id: int, direction: str) -> None:
        self.pending_actor = actor
        self.pending_color = color
        self.pending_id = block_id
        self.pending_dir = direction
        self.pending_x = None
        self.pending_y = None

    def _clear_pending(self) -> None:
        self.pending_actor = None
        self.pending_color = None
        self.pending_id = None
        self.pending_dir = None
        self.pending_x = None
        self.pending_y = None
        self.pending_user_prompt = None

    def _has_pending(self) -> bool:
        return self.pending_actor is not None and self.pending_color is not None and self.pending_id is not None

    def _pending_matches(self, actor: str, color: str, sid: str) -> bool:
        if not self._has_pending():
            return False
        try:
            block_id = int(sid)
        except ValueError:
            return False
        return (
            self.pending_actor == actor
            and self.pending_color == color
            and self.pending_id == block_id
        )

    def _update_state_cache(self, state_msg: str) -> None:
        # state <phase> blocks <c:id:x:y;...> goals <x:y;...>
        try:
            _, rest = state_msg.split(" ", 1)
            _, rest = rest.split(" blocks ", 1)
            blocks_part, _ = rest.split(" goals ", 1)
        except ValueError:
            return

        positions: dict[tuple[str, int], tuple[int, int]] = {}
        if blocks_part and blocks_part != "-":
            for token in blocks_part.split(";"):
                try:
                    color, sid, sx, sy = token.split(":")
                    positions[(color, int(sid))] = (int(sx), int(sy))
                except ValueError:
                    continue
        self.last_positions = positions

    def _fail(self, reason: str) -> None:
        self.get_logger().error(reason)
        self.mode = "await_fixed"
        self._publish(
            self.nlp_in_pub,
            "An error occurred, please check the modules. Say fixed to continue.",
            "/nlp/in",
        )

    def _publish(self, pub, text: str, topic: str) -> None:
        msg = String()
        msg.data = text
        pub.publish(msg)
        self.get_logger().info(f"WRITE {topic}: {text}")


def main() -> None:
    rclpy.init()
    node = Orchestrator()
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
