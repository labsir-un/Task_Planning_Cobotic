from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from Main.ros_constants import TOPIC_ABB_COMMAND, TOPIC_ABB_RESULT
from Main import ros_constants as cfg


class AbbBridge(Node):
    def __init__(self) -> None:
        super().__init__("abb_bridge")
        self.host = cfg.ABB_HOST
        self.port = cfg.ABB_PORT
        self.timeout = cfg.ABB_TIMEOUT
        self.sock: socket.socket | None = None
        self.lock = threading.Lock()
        self.create_subscription(String, TOPIC_ABB_COMMAND, self._on_command, 10)
        self.result_pub = self.create_publisher(String, TOPIC_ABB_RESULT, 10)
        self._connect()

    def _connect(self) -> None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            self.sock = s
            self.get_logger().info(f"Connected to ABB at {self.host}:{self.port}")
        except Exception as exc:
            self.get_logger().error(f"Failed to connect to ABB: {exc}")
            self.sock = None

    def _on_command(self, msg: String) -> None:
        payload = msg.data.strip()
        self.get_logger().info(f"Received abb/command: {payload}")
        try:
            data = json.loads(payload)
            # Expected: {"color": str, "id": int, "dir": str}
        except Exception as exc:
            self.get_logger().error(f"Invalid JSON on abb/command: {exc}")
            return
        tcp_string = self._format_tcp_string(data)
        if tcp_string is None:
            self.get_logger().error("abb/command missing x/y/dir fields")
            self._publish_result(False)
            return
        self.get_logger().info(f"TCP payload: {tcp_string}")
        self._send_to_abb(tcp_string)

    def _format_tcp_string(self, data: dict) -> str | None:
        try:
            x = int(data.get("x"))
            y = int(data.get("y"))
            direction = str(data.get("dir"))
        except Exception:
            return None
        if direction not in {"up", "down", "left", "right"}:
            return None
        dir_char = direction[0].upper()
        return f"{x:02d}{y:02d}{dir_char}"

    def _send_to_abb(self, text: str) -> None:
        if self.sock is None:
            self._connect()
        if self.sock is None:
            self._publish_result(False)
            return
        try:
            with self.lock:
                self.sock.sendall(text.encode())
                reply = self.sock.recv(1024)
            ok = reply.strip() == b"1"
            self.get_logger().info(f"ABB reply: {reply!r}, ok={ok}")
            self._publish_result(ok)
        except Exception as exc:
            self.get_logger().error(f"ABB send error: {exc}")
            self._publish_result(False)
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _publish_result(self, ok: bool) -> None:
        msg = String()
        msg.data = json.dumps({"ok": bool(ok)})
        self.result_pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = AbbBridge()
    executor = SingleThreadedExecutor()
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
