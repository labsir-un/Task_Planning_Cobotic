from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from buildCif import enumerate_instances
from game_types import ActorType, Direction, Position, DOWN, LEFT, RIGHT, UP


def _direction_label(direction: Direction) -> str:
    if direction == UP:
        return "up"
    if direction == DOWN:
        return "down"
    if direction == LEFT:
        return "left"
    if direction == RIGHT:
        return "right"
    raise ValueError(f"Unknown direction {direction}")


class SupervisorBridge:
    """Runs cifsim and gates moves through the supervisory controller."""

    def __init__(self, proc: subprocess.Popen[str], instance_positions: dict[str, Position], master_fd: int, log_path: Path) -> None:
        self.proc = proc
        self.instance_positions = instance_positions  # instance -> position
        self.allowed_events: dict[str, int] = {}
        self.master_fd = master_fd
        self.log_path = log_path

    @classmethod
    def start(cls, board, instances: Optional[list[tuple[str, object, Position]]] = None) -> "SupervisorBridge":
        if instances is None:
            instances = enumerate_instances(board)
        instance_positions = {name: pos for name, _, pos in instances}
        base_cmd = ["../../../EclipseEscet/eclipse-escet-v9.0/bin/cifsim", "./sokoban.cif", "--input-mode=console"]
        log_path = Path("/tmp/supervisor_cif.log")
        try:
            log_path.unlink()
        except FileNotFoundError:
            pass
        log_path.touch(exist_ok=True)
        try:
            log_path.write_text("Supervisor started\n")
        except Exception:
            pass
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            base_cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        try:
            with log_path.open("a") as log_file:
                log_file.write(f"Spawned supervisor PID {proc.pid} using command: {' '.join(base_cmd)}\n")
        except Exception:
            pass
        # Launch a terminal to tail the log for visibility
        try:
            subprocess.Popen(
                ["gnome-terminal", "--", "bash", "-lc", f"tail -F {log_path}; exec bash"],
                close_fds=True,
            )
        except FileNotFoundError:
            print("gnome-terminal not found; supervisor log will only appear in this console.")
        bridge = cls(proc, instance_positions, master_fd, log_path)
        bridge._read_until_prompt()
        return bridge

    def shutdown(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        try:
            os.close(self.master_fd)
        except Exception:
            pass
        try:
            with self.log_path.open("a") as log_file:
                log_file.write("Supervisor shutdown\n")
        except Exception:
            pass

    def request_move(self, start_pos: Position, direction: Direction, actor: ActorType) -> bool:
        if self.proc.poll() is not None:
            print("Supervisor process is not running", file=sys.stderr)
            print("Avoid move! Supervisory prohibits")
            return False
        instance = self._instance_for_position(start_pos)
        if instance is None:
            print("Avoid move! Supervisory prohibits (unknown instance)")
            return False
        label = _direction_label(direction)
        if actor == ActorType.PLAYER:
            label = f"{label}_user"
        event = f"{instance}.{label}"
        number = self.allowed_events.get(event)
        if number is None:
            print("Avoid move! Supervisory prohibits")
            return False
        try:
            os.write(self.master_fd, f"{number}\n".encode())
        except Exception as exc:
            print(f"Failed to send to supervisor: {exc}", file=sys.stderr)
            return False
        self._read_until_prompt()
        return True

    def update_position(self, start_pos: Position, direction: Direction) -> None:
        instance = self._instance_for_position(start_pos)
        if instance is None:
            return
        new_pos = (start_pos[0] + direction.dx, start_pos[1] + direction.dy)
        self.instance_positions[instance] = new_pos

    def _instance_for_position(self, pos: Position) -> Optional[str]:
        for name, inst_pos in self.instance_positions.items():
            if inst_pos == pos:
                return name
        return None

    def _read_until_prompt(self) -> None:
        lines: list[str] = []
        while True:
            if self.proc.poll() is not None:
                try:
                    with self.log_path.open("a") as log_file:
                        log_file.write(f"Supervisor exited with code {self.proc.returncode}\n")
                except Exception:
                    pass
                break
            ready, _, _ = select.select([self.master_fd], [], [], 0.1)
            if not ready:
                continue
            try:
                chunk = os.read(self.master_fd, 4096)
            except OSError:
                break
            if not chunk:
                continue
            for raw_line in chunk.decode(errors="ignore").splitlines():
                cleaned = raw_line.rstrip("\r\n")
                if cleaned == "":
                    continue
                lines.append(cleaned)
                try:
                    with self.log_path.open("a") as log_file:
                        log_file.write(cleaned + "\n")
                except Exception:
                    pass
                if cleaned.startswith("Select a transition"):
                    self._parse_allowed_events(lines)
                    return
        self._parse_allowed_events(lines)

    def _parse_allowed_events(self, lines: list[str]) -> None:
        pattern = re.compile(r"#\s*(\d+):\s*event\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)")
        allowed: dict[str, int] = {}
        for line in lines:
            match = pattern.search(line)
            if match:
                number = int(match.group(1))
                event = f"{match.group(2)}.{match.group(3)}"
                allowed[event] = number
        if not allowed and lines:
            try:
                with self.log_path.open("a") as log_file:
                    log_file.write("Warning: supervisor returned no transitions; output was:\n")
                    for l in lines:
                        log_file.write(l + "\n")
            except Exception:
                pass
        self.allowed_events = allowed
