# NLP Voice Interface

Minimal voice + TTS helpers for yes/no answers and short commands. Uses the microphone via Vosk (offline STT) and `pyttsx3` for speech synthesis. Communicates over ROS 2 topics as simple strings.

## Files
- `main.py` — ROS 2 node: listens, maps to commands, publishes to `nlp/command`, subscribes to `nlp/message`, speaks mapped inbound messages.
- `voice_to_text.py` — `listen_and_classify()` helper using offline Vosk STT, returns `(text, label)`.
- `text_to_speech.py` — `say()` and `init_engine()` helpers using `pyttsx3`.
- `Main.py` — legacy experimental script (not used in integration).
- `README.md` — this file.

## Setup
- Create a venv at repo root if needed: `python3 -m venv venv`
- System deps for microphone (PortAudio): `sudo apt-get install -y libportaudio2 portaudio19-dev`
- Install Python deps without activating the venv: `./venv/bin/pip install speechrecognition pyaudio pyttsx3 vosk rclpy`
- Download a Vosk model (e.g., small English): `https://alphacephei.com/vosk/models` and unpack it to `./models/vosk-model-small-en-us-0.15` (hardcoded path used by the code).
- If you place the model elsewhere, move/symlink it to that default location.
- Ensure microphone access; no internet required for STT once the model is present.
- ROS 2 environment must be sourced (e.g., `source /opt/ros/<distro>/setup.bash`).

## Run
- `./venv/bin/python NLP/main.py`
- Behavior:
  - Continuous audio loop (no terminal prompts).
  - Listens for voice, maps to hardcoded commands:
    - `start`
    - `move <color> <id> <dir>` (color: blue/green, dir: up/down/left/right)
  - Publishes string messages on `nlp/command`.
  - Subscribes to `nlp/message` (String) and speaks mapped responses via `pyttsx3`.
  - Uses offline Vosk STT. Model path defaults to `NLP/models/vosk-model-small-en-us-0.15`; adjust `device` in `main.py` if you need a specific mic index.

## Test
- Send messages to the NLP module with
  - `ros2 topic pub /nlp/message std_msgs/msg/String "{data: 'MESSAGE HERE'}" --once`
