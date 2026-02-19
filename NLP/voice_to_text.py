from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Optional

import speech_recognition as sr

try:
    import vosk  # type: ignore
except ImportError:
    vosk = None  # typed for optional import
else:
    # Silence Vosk engine logs (Kaldi/Vosk INFO lines).
    vosk.SetLogLevel(-1)

# Minimal voice-to-text helper focused on yes/no or short commands.
# Listening flow mirrors the working escuchar_comando implementation.

YES_WORDS = {"yes", "affirmative"}
NO_WORDS = {"no", "negative"}

DEFAULT_MODEL_PATH = "/home/feli/Documents/Tesis/NLP/model/vosk-model-small-en-us-0.15"

_VOSK_MODEL: Optional[object] = None
_VOSK_MODEL_PATH: Optional[str] = None


@contextlib.contextmanager
def _suppress_stderr_fd() -> None:
    """
    Suppress low-level ALSA/PortAudio stderr noise during mic operations.
    """
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        saved_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 2)
    except Exception:
        # Fallback: continue without suppression.
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


def _load_vosk_model(path: str) -> Optional[object]:
    global _VOSK_MODEL, _VOSK_MODEL_PATH
    if vosk is None:
        print("Vosk is not installed. Run: ./venv/bin/pip install vosk")
        return None
    if _VOSK_MODEL is None or _VOSK_MODEL_PATH != path:
        try:
            _VOSK_MODEL = vosk.Model(path)
            _VOSK_MODEL_PATH = path
        except Exception as exc:
            print(f"Failed to load Vosk model at {path}: {exc}")
            return None
    return _VOSK_MODEL


def _recognize_offline(
    audio: sr.AudioData,
    model_path: str,
    allowed_words: list[str] | None = None,
) -> tuple[str | None, str]:
    model = _load_vosk_model(model_path)
    if model is None:
        return None, "error"
    try:
        if allowed_words:
            grammar_json = json.dumps(allowed_words)
            recognizer = vosk.KaldiRecognizer(model, audio.sample_rate, grammar_json)
        else:
            recognizer = vosk.KaldiRecognizer(model, audio.sample_rate)
        recognizer.SetWords(True)
        if not recognizer.AcceptWaveform(audio.get_raw_data()):
            result = recognizer.FinalResult()
        else:
            result = recognizer.Result()
        data = json.loads(result)
        text = data.get("text", "").strip()
        if not text:
            return None, "unknown"
        print(f"Detected text: {text}")
        return text, "ok"
    except Exception as exc:
        print(f"Offline recognition error: {exc}")
        return None, "error"


def listen_and_classify(
    timeout: float = 5.0,
    device_index: int | None = None,
    allowed_words: list[str] | None = None,
    phrase_time_limit: float | None = 2.5,
) -> tuple[str | None, str]:
    """
    Capture speech and return recognized text plus a coarse label.

    Returns:
        (text, label)
        text: recognized string or None if unintelligible.
        label: "yes", "no", "unknown", or "error".
    """
    recognizer = sr.Recognizer()
    # Keep ambient noise calibration, matching escuchar_comando behavior.
    with _suppress_stderr_fd():
        with sr.Microphone(device_index=device_index) as source:
            print("Listening...")
            with contextlib.suppress(Exception):
                recognizer.adjust_for_ambient_noise(source)
            try:
                audio = recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
            except sr.WaitTimeoutError:
                print("No audio detected.")
                return None, "unknown"

    model_path = str(DEFAULT_MODEL_PATH)
    if not Path(model_path).exists():
        print(f"Vosk model not found at {model_path}. Place the model at this path.")
        return None, "error"

    text, status = _recognize_offline(audio, model_path, allowed_words=allowed_words)
    if status == "error":
        return None, "error"
    if text is None:
        print("Could not understand audio.")
        return None, "unknown"

    lowered = text.lower()
    if any(word in lowered for word in YES_WORDS):
        return text, "yes"
    if any(word in lowered for word in NO_WORDS):
        return text, "no"
    return text, "unknown"


if __name__ == "__main__":
    text, label = listen_and_classify()
    print(f"Heard: {text!r}, classified: {label}")
