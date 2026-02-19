from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_PIPER_MODEL_PATH = "/home/feli/Documents/Tesis/NLP/model/en_US-amy-medium.onnx"


@contextlib.contextmanager
def _suppress_stderr_fd() -> None:
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        saved_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 2)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            os.dup2(saved_stderr_fd, 2)
        with contextlib.suppress(Exception):
            os.close(saved_stderr_fd)
        with contextlib.suppress(Exception):
            os.close(devnull_fd)


def init_engine(rate: int | None = 170, volume: float | None = 0.9, voice: str | None = None) -> dict[str, Any]:
    # kept for API compatibility
    del rate, volume, voice
    venv_piper = Path(sys.executable).parent / "piper"
    piper_bin = str(venv_piper) if venv_piper.exists() else None
    aplay_bin = "aplay"
    model_path = Path(DEFAULT_PIPER_MODEL_PATH)
    if piper_bin is None:
        raise RuntimeError("Piper binary not found at NLP venv path: ./venv/bin/piper")
    if not model_path.exists():
        raise RuntimeError(f"Piper model not found at {model_path}.")
    config_path = Path(f"{model_path}.json")
    if not config_path.exists():
        raise RuntimeError(
            "Piper model config missing. Expected file: "
            f"{config_path}. Download both files for the same voice: .onnx and .onnx.json"
        )
    probe = subprocess.run(
        [piper_bin, "--help"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if probe.returncode != 0:
        err = (probe.stderr or "").strip()
        if "No module named 'pathvalidate'" in err:
            raise RuntimeError(
                "Piper installation is incomplete. Install missing dependency in NLP venv: "
                "./venv/bin/pip install pathvalidate"
            )
        raise RuntimeError(f"Piper binary failed to start: {err}")
    return {
        "backend": "piper",
        "piper_bin": piper_bin,
        "aplay_bin": aplay_bin,
        "model_path": str(model_path),
    }


def say(text: str, engine: dict[str, Any] | None = None, wait: bool = True) -> dict[str, Any]:
    local_engine = engine or init_engine()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    try:
        synth = subprocess.run(
            [
                local_engine["piper_bin"],
                "--model",
                local_engine["model_path"],
                "--output_file",
                wav_path,
            ],
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        if synth.returncode != 0:
            err = (synth.stderr or b"").decode(errors="ignore").strip()
            raise RuntimeError(f"Piper synthesis failed: {err}")

        play_cmd = [local_engine["aplay_bin"], wav_path]
        with _suppress_stderr_fd():
            if wait:
                subprocess.run(play_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                subprocess.Popen(
                    play_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
    finally:
        with contextlib.suppress(Exception):
            os.unlink(wav_path)
    return local_engine


if __name__ == "__main__":
    eng = init_engine()
    say("Voice preview from NLP text to speech.", eng)
