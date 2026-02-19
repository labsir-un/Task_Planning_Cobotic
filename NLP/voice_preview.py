from __future__ import annotations

import re

import pyttsx3


PHRASE = "Hello, this is a voice preview for the cobot experiment."


def is_english_voice(voice: pyttsx3.voice.Voice) -> bool:
    text = f"{voice.id} {voice.name} {' '.join(map(str, voice.languages))}".lower()
    return bool(re.search(r"\ben\b|english", text))


def main() -> None:
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    english = [v for v in voices if is_english_voice(v)]

    if not english:
        print("No English voices detected. Showing all voices instead.")
        english = voices

    print(f"Found {len(english)} candidate voices.")
    print("Press Enter for next voice, or type q + Enter to quit.\n")

    for idx, voice in enumerate(english, start=1):
        print(f"[{idx}/{len(english)}] name={voice.name} | id={voice.id}")
        engine.setProperty("voice", voice.id)
        engine.say(PHRASE)
        engine.runAndWait()
        ans = input("Next? ").strip().lower()
        if ans == "q":
            break


if __name__ == "__main__":
    main()
