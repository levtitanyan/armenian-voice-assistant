"""Speech-to-text helpers: microphone recording and Armenian transcription."""

from __future__ import annotations

import os
import select
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

try:
    from .common import PROJECT_ROOT, display_path, is_mostly_armenian
except ImportError:  # pragma: no cover - supports direct script execution
    from common import PROJECT_ROOT, display_path, is_mostly_armenian

VOICE_INPUT_DIR = PROJECT_ROOT / "data" / "conversations" / "voice_input"
SAMPLE_RATE = 16000
MIN_ARMENIAN_RATIO = 0.45
MIN_ARMENIAN_LETTERS = 2


class StopConversationRequested(Exception):
    """Raised when the user presses Esc during recording."""


def _wait_for_recording_key() -> str:
    """Wait for Enter (finish turn) or Esc (stop conversation)."""
    if not sys.stdin.isatty():
        input()
        return "enter"

    try:
        import termios
        import tty
    except ImportError:
        input()
        return "enter"

    fd = sys.stdin.fileno()
    original_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                continue

            char = sys.stdin.read(1)
            if char in ("\n", "\r"):
                return "enter"
            if char == "\x1b":
                return "esc"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_attrs)


def _get_elevenlabs_client() -> ElevenLabs:
    """Create an ElevenLabs client from `.env`/environment variables."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def record_voice_to_wav(
    output_path: Path,
    sample_rate: int = SAMPLE_RATE,
    show_saved_message: bool = False,
) -> Path:
    """Record microphone audio until Enter/Esc and save a WAV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []

    def callback(indata, frames_count, time_info, status) -> None:  # type: ignore[no-untyped-def]
        if status:
            print(status)
        frames.append(indata.copy())

    print("Recording... press Enter to finish turn, Esc to stop conversation.")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", callback=callback):
        stop_key = _wait_for_recording_key()

    if stop_key == "esc":
        raise StopConversationRequested("Esc pressed during recording.")

    if not frames:
        raise RuntimeError("No audio captured from microphone.")

    audio_np = np.concatenate(frames, axis=0)
    sf.write(output_path.as_posix(), audio_np, sample_rate, subtype="PCM_16")
    if show_saved_message:
        print(f"Saved voice recording: {display_path(output_path)}")
    return output_path


def transcribe_armenian(audio_path: Path, model_id: str = "scribe_v2") -> str:
    """Transcribe an audio file and return Armenian text only."""
    client = _get_elevenlabs_client()
    with audio_path.open("rb") as audio_file:
        transcription = client.speech_to_text.convert(
            file=audio_file,
            model_id=model_id,
            language_code="hye",
        )

    text = getattr(transcription, "text", None)
    if not text:
        text = str(transcription)

    cleaned = text.strip()
    if not cleaned:
        return ""

    if not is_mostly_armenian(
        cleaned,
        min_ratio=MIN_ARMENIAN_RATIO,
        min_armenian_letters=MIN_ARMENIAN_LETTERS,
    ):
        return ""

    return cleaned


def record_and_transcribe_armenian(filename: str = "mic.wav") -> tuple[Path, str]:
    """Convenience helper: record one turn and transcribe it."""
    output_path = VOICE_INPUT_DIR / filename
    wav_path = record_voice_to_wav(output_path=output_path)
    transcript = transcribe_armenian(wav_path)
    return wav_path, transcript


def main() -> None:
    """Manual CLI smoke test for local development."""
    wav_path, transcript = record_and_transcribe_armenian()
    print(f"Transcription from {display_path(wav_path)}:")
    print(transcript)


if __name__ == "__main__":
    main()
