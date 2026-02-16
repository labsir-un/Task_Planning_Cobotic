from __future__ import annotations

import json
import sys
from pathlib import Path

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from Main.ros_constants import (
    TOPIC_CIF_MOVE,
    TOPIC_CIF_MOVE_EVENT,
    TOPIC_CIF_START,
    TOPIC_NLP_COMMAND,
    TOPIC_NLP_MESSAGE,
)


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _parse_int_token(token: str) -> int | None:
    token = token.lower()
    try:
        return int(token)
    except Exception:
        return NUMBER_WORDS.get(token)


class Orchestrator(Node):
    def __init__(self) -> None:
        super().__init__("orchestrator")
        self.create_subscription(String, TOPIC_CIF_MOVE_EVENT, self._on_cif_move_event, 10)
        self.create_subscription(String, TOPIC_NLP_COMMAND, self._on_nlp_command, 10)
        self.cif_start_pub = self.create_publisher(String, TOPIC_CIF_START, 10)
        self.cif_move_pub = self.create_publisher(String, TOPIC_CIF_MOVE, 10)
        self.nlp_message_pub = self.create_publisher(String, TOPIC_NLP_MESSAGE, 10)

    def _on_cif_move_event(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        actor = data.get("actor")
        color = data.get("color")
        block_id = data.get("id")
        direction = data.get("dir")
        if actor == "agent" and color == "red" and block_id is not None and direction:
            speak = f"Robot will move red block number {block_id} {direction}, please wait..."
            self._publish_nlp_message(speak)
        else:
            self.get_logger().info(f"Move event: {data}")

    def _publish_nlp_message(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.nlp_message_pub.publish(msg)
        self.get_logger().info(f"Sent NLP message: {text}")

    def _on_nlp_command(self, msg: String) -> None:
        text = msg.data.strip().lower()
        self.get_logger().info(f"Received NLP command: {text}")
        if text == "start":
            self.cif_start_pub.publish(String(data=""))
            self.get_logger().info("Received NLP start; forwarded to cif/start")
            return
        if text.startswith("move "):
            parts = text.split()
            # expected: move <color> <id> <dir>
            if len(parts) != 4:
                self.get_logger().info(f"Ignored NLP move (wrong parts): {parts}")
                return
            _, color, num, direction = parts
            block_id = _parse_int_token(num)
            if block_id is None:
                self.get_logger().info(f"Ignored NLP move (bad id): {num}")
                return
            payload = {"color": color, "id": block_id, "dir": direction}
            self._publish_cif_move(payload)
            self.get_logger().info(f"Forwarded move to cif/move: {payload}")
        else:
            self.get_logger().info(f"Ignored NLP command: {text}")

    def _publish_cif_move(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload)
        self.cif_move_pub.publish(msg)


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
    import json
    main()
