from __future__ import annotations

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

from Orchestrator import ros_constants as cfg
from Orchestrator.ros_constants import TOPIC_ABB_IN, TOPIC_ABB_OUT, TOPIC_ABB_START


class AbbBridge(Node):
    def __init__(self) -> None:
        super().__init__("abb_bridge")
        self.host = cfg.ABB_HOST
        self.port = cfg.ABB_PORT
        self.timeout = cfg.ABB_TIMEOUT
        self.test_mode = bool(cfg.ABB_TEST_MODE)
        self.sock: socket.socket | None = None
        self.lock = threading.Lock()

        self.create_subscription(String, TOPIC_ABB_START, self._on_start, 10)
        self.create_subscription(String, TOPIC_ABB_IN, self._on_in, 10)
        self.out_pub = self.create_publisher(String, TOPIC_ABB_OUT, 10)
        self.get_logger().info(f"ABB module started. test_mode={self.test_mode}")

    def _on_start(self, _: String) -> None:
        if self.test_mode:
            self.get_logger().info("PROCESS test mode active, skipping TCP connect on start.")
            return
        self.get_logger().info("PROCESS start received, connecting TCP socket.")
        self._connect()
        if self.sock is None:
            self.get_logger().error("PROCESS start connect failed, publishing fail.")
            self._publish_out("fail")

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

    def _on_in(self, msg: String) -> None:
        raw = msg.data.strip()
        text = raw.lower()
        self.get_logger().info(f"READ /abb/in: {raw}")
        if self.test_mode:
            self.get_logger().info("PROCESS test mode active, returning ABB ok immediately.")
            self._publish_out("ok")
            return
        if raw == "XXXXX" or text == "xxxxx":
            self.get_logger().info("PROCESS formatting special space payload.")
            ok = self._send_to_abb("XXXXX")
            self._publish_out("ok" if ok else "fail")
            return
        parts = text.split()
        if len(parts) != 4 or parts[0] != "move":
            self.get_logger().error("Invalid ABB input format. Expected: move <x> <y> <dir>")
            self._publish_out("fail")
            return
        _, sx, sy, direction = parts
        if direction not in {"up", "down", "left", "right"}:
            self.get_logger().error(f"Invalid direction: {direction}")
            self._publish_out("fail")
            return
        try:
            x = int(sx)
            y = int(sy)
        except ValueError:
            self.get_logger().error("Invalid x/y in ABB input.")
            self._publish_out("fail")
            return

        self.get_logger().info("PROCESS formatting move payload.")
        tcp_payload = f"{x:02d}{y:02d}{direction[0].upper()}"
        self.get_logger().info(f"TCP payload: {tcp_payload}")
        ok = self._send_to_abb(tcp_payload)
        self._publish_out("ok" if ok else "fail")

    def _send_to_abb(self, payload: str) -> bool:
        if self.sock is None:
            self._connect()
        if self.sock is None:
            return False
        try:
            with self.lock:
                self.get_logger().info("PROCESS sending payload over TCP.")
                self.sock.sendall(payload.encode())
                reply = self.sock.recv(1024).strip()
            self.get_logger().info(f"ABB reply: {reply!r}")
            return reply == b"1"
        except Exception as exc:
            self.get_logger().error(f"ABB send error: {exc}")
            try:
                if self.sock is not None:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None
            return False

    def _publish_out(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.out_pub.publish(msg)
        self.get_logger().info(f"WRITE /abb/out: {text}")


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
