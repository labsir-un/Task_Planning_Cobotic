from __future__ import annotations

import pyttsx3


def init_engine(rate: int | None = 170, volume: float | None = 0.9, voice: str | None = None) -> pyttsx3.Engine:
    """
    Initialize a TTS engine.

    rate: words per minute (approx). None to keep default.
    volume: 0.0-1.0. None to keep default.
    voice: optional voice id; leave None to use system default.
    """
    engine = pyttsx3.init()
    if rate is not None:
        engine.setProperty("rate", rate)
    if volume is not None:
        engine.setProperty("volume", volume)
    if voice is not None:
        engine.setProperty("voice", voice)
    return engine


def say(text: str, engine: pyttsx3.Engine | None = None, wait: bool = True) -> pyttsx3.Engine:
    """
    Speak text using pyttsx3.

    If no engine is provided, a new one is created (and returned).
    Set wait=False to enqueue speech without blocking.
    """
    local_engine = engine or init_engine()
    local_engine.say(text)
    if wait:
        local_engine.runAndWait()
    return local_engine


if __name__ == "__main__":
    eng = init_engine()
    say("Hola, estoy listo para colaborar contigo.", eng)
