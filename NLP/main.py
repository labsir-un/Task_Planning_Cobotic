from __future__ import annotations

from threading import Thread
import time
import sys
from pathlib import Path
from enum import Enum

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from Main.ros_constants import TOPIC_NLP_COMMAND, TOPIC_NLP_MESSAGE

from text_to_speech import say, init_engine
from voice_to_text import listen_and_classify


class UserCommand(str):
    START = "start"
    MOVE = "move"


COMMAND_KEYWORDS = {
    UserCommand.START: ("start", "go", "begin"),
    UserCommand.MOVE: ("move", "mover"),
}


class IncomingMessage(Enum):
    REQUEST_CONFIRM = "request_confirm"
    TASK_DONE = "task_done"
    ERROR = "error"


INCOMING_SPEECH = {
    IncomingMessage.REQUEST_CONFIRM: "Please confirm: should I continue?",
    IncomingMessage.TASK_DONE: "Task completed.",
    IncomingMessage.ERROR: "There was an error. Please check the system.",
}


def map_text_to_command(text: str | None) -> UserCommand | None:
    if not text:
        return None
    lowered = text.lower()
    for cmd, keywords in COMMAND_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            return cmd
    return None


def map_message_to_enum(message: str) -> IncomingMessage | None:
    for msg in IncomingMessage:
        if message == msg.value:
            return msg
    return None


class NlpNode(Node):
    def __init__(self) -> None:
        super().__init__("nlp_node")
        self.engine = init_engine()
        self.device_index = None  # set to mic index if needed
        self.command_pub = self.create_publisher(String, TOPIC_NLP_COMMAND, 10)
        self.create_subscription(String, TOPIC_NLP_MESSAGE, self._on_message, 10)
        say("Voice interface ready.", self.engine)

    def listen_and_publish(self) -> None:
        text, _ = listen_and_classify(device_index=self.device_index, timeout=3.0)
        cmd = map_text_to_command(text)
        if cmd == UserCommand.START:
            msg = String()
            msg.data = UserCommand.START
            self.command_pub.publish(msg)
            say("Starting the system.", self.engine)
        elif cmd == UserCommand.MOVE:
            # crude parse: expect "move <color> <id> <dir>"
            parts = text.lower().split()
            if len(parts) == 4 and parts[0] in COMMAND_KEYWORDS[UserCommand.MOVE]:
                _, color, num, direction = parts
                msg = String()
                msg.data = f"move {color} {num} {direction}"
                self.command_pub.publish(msg)
                say(f"Moving {color} {num} {direction}", self.engine)

    def _on_message(self, msg: String) -> None:
        mapped = map_message_to_enum(msg.data)
        if mapped:
            speech = INCOMING_SPEECH.get(mapped, f"Message: {mapped.value}")
        else:
            speech = f"Received message: {msg.data}"
        say(speech, self.engine)


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
