from __future__ import annotations

import subprocess
from pathlib import Path


LAUNCH_ORDER = [
    "Orchestrator",
    "ABB",
    "NLP",
    "Planner",
    "GridTwin",
]


def _open_module_terminal(repo_root: Path, module: str) -> None:
    module_dir = repo_root / module
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{module.lower()}.log"
    cmd = (
        "cd '{}' && ./venv/bin/python ./main.py 2>&1 | tee -a '{}'; exec bash".format(
            module_dir, log_file
        )
    )
    subprocess.Popen(
        ["gnome-terminal", "--", "bash", "-lc", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    for module in LAUNCH_ORDER:
        _open_module_terminal(repo_root, module)


if __name__ == "__main__":
    main()
