from __future__ import annotations

import sys
import time
from pathlib import Path
from threading import Thread

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from Orchestrator.ros_constants import TOPIC_NLP_IN, TOPIC_NLP_OUT
from text_to_speech import init_engine, say
from voice_to_text import listen_and_classify

ALLOWED_COMMANDS = ["start", "go", "fixed", "done", "space"]


def map_text_to_token(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower().strip()
    if "start" in lowered:
        return "start"
    if "go" in lowered:
        return "go"
    if "fixed" in lowered:
        return "fixed"
    if "done" in lowered:
        return "done"
    if "space" in lowered:
        return "space"
    return None


class NlpNode(Node):
    def __init__(self) -> None:
        super().__init__("nlp_node")
        self.engine = init_engine()
        self.device_index = None
        self.awaiting_response = False
        self.started = False
        self.listen_enabled = True  # Enabled initially to capture "start".
        self.last_prompt_text = ""
        self.last_prompt_ts = 0.0
        self.out_pub = self.create_publisher(String, TOPIC_NLP_OUT, 10)
        self.create_subscription(String, TOPIC_NLP_IN, self._on_in, 10)
        self.get_logger().info("NLP module started.")
        say("Voice interface ready.", self.engine)

    def listen_and_publish(self) -> None:
        if not self.listen_enabled:
            return
        self.get_logger().info("PROCESS listening for user input...")
        text, _ = listen_and_classify(
            device_index=self.device_index,
            timeout=3.0,
            allowed_words=ALLOWED_COMMANDS,
            phrase_time_limit=2.5,
        )
        token = map_text_to_token(text)
        if token is None:
            if self.awaiting_response and (time.time() - self.last_prompt_ts) >= 5.0 and self.last_prompt_text:
                self.get_logger().info("PROCESS user timeout exceeded 5s, repeating prompt.")
                say(self.last_prompt_text, self.engine)
                self.last_prompt_ts = time.time()
            return
        self.get_logger().info("PROCESS acknowledging instruction before publish.")
        say("Instruction received.", self.engine)
        msg = String()
        msg.data = token
        self.out_pub.publish(msg)
        self.get_logger().info(f"WRITE /nlp/out: {token}")
        self.awaiting_response = False
        if token == "start":
            self.started = True
            self.listen_enabled = False
        else:
            self.listen_enabled = False

    def _on_in(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"READ /nlp/in: {text}")
        self.get_logger().info("PROCESS speaking incoming message.")
        say(text, self.engine)
        self.last_prompt_text = text
        lowered = text.lower()
        if "say " in lowered or "confirm" in lowered:
            self.awaiting_response = True
            self.last_prompt_ts = time.time()
            self.listen_enabled = True
        else:
            self.awaiting_response = False
            # Keep start listening enabled until system is started.
            self.listen_enabled = not self.started


def main() -> None:
    rclpy.init()
    node = NlpNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    def spin() -> None:
        executor.spin()

    spin_thread = Thread(target=spin, daemon=True)
    spin_thread.start()

    try:
        while rclpy.ok():
            node.listen_and_publish()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
