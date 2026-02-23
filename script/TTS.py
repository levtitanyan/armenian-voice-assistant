"""Text-to-speech helpers for generated replies and prebuilt FAQ audio."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

try:
    from .common import PROJECT_ROOT, display_path
except ImportError:  # pragma: no cover - supports direct script execution
    from common import PROJECT_ROOT, display_path

TTS_OUTPUT_DIR = PROJECT_ROOT / "data" / "conversations" / "tts_output"


def _get_elevenlabs_client() -> ElevenLabs:
    """Create an ElevenLabs client from `.env`/environment variables."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def _play_audio_if_available(audio_bytes: bytes, playback: bool = True) -> None:
    """Play MP3 bytes when playback is enabled and local player is available."""
    if not playback:
        return

    if shutil.which("ffplay"):
        play(audio_bytes)
    else:
        print("Playback skipped: ffplay not found.")


def synthesize_armenian_mp3(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
) -> tuple[Path, bytes]:
    """Synthesize Armenian text to MP3 and return file path + audio bytes."""
    if output_path is None:
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = TTS_OUTPUT_DIR / output_filename
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    client = _get_elevenlabs_client()
    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format="mp3_44100_128",
        language_code="hy",
    )
    audio_bytes = b"".join(audio_stream)
    output_path.write_bytes(audio_bytes)
    return output_path, audio_bytes


def play_prebuilt_audio(
    audio_path: Path,
    output_path: Path | None = None,
    playback: bool = True,
    show_used_message: bool = True,
) -> Path:
    """Play (and optionally copy) a pre-recorded MP3 answer file."""
    if not audio_path.exists():
        raise FileNotFoundError(f"Pre-recorded audio not found: {audio_path}")

    if output_path is None:
        target_path = audio_path
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_path = output_path
        if audio_path.resolve() != output_path.resolve():
            shutil.copyfile(audio_path, output_path)

    audio_bytes = target_path.read_bytes()
    if show_used_message:
        print(f"Used pre-recorded FAQ voice: {display_path(audio_path)}")

    _play_audio_if_available(audio_bytes=audio_bytes, playback=playback)
    return target_path


def speak_armenian(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
    playback: bool = True,
    show_saved_message: bool = False,
) -> Path:
    """Generate and optionally play Armenian TTS for assistant output."""
    output_path, audio_bytes = synthesize_armenian_mp3(
        text=text,
        output_filename=output_filename,
        output_path=output_path,
        voice_id=voice_id,
        model_id=model_id,
    )

    if show_saved_message:
        print(f"Saved reply audio: {display_path(output_path)}")

    _play_audio_if_available(audio_bytes=audio_bytes, playback=playback)
    return output_path


def main() -> None:
    """Manual CLI smoke test for local development."""
    sample_text = "Բարև, ես փորձնական պատասխան եմ հայերենով։"
    speak_armenian(sample_text)


if __name__ == "__main__":
    main()
