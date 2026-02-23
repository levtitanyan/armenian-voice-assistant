import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TTS_OUTPUT_DIR = PROJECT_ROOT / "io" / "tts_output"


def _display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
        return f"{PROJECT_ROOT.name}/{relative.as_posix()}"
    except ValueError:
        return str(path)


def _get_elevenlabs_client() -> ElevenLabs:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def synthesize_armenian_mp3(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
) -> tuple[Path, bytes]:
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


def speak_armenian(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
    playback: bool = True,
    show_saved_message: bool = False,
) -> Path:
    output_path, audio_bytes = synthesize_armenian_mp3(
        text=text,
        output_filename=output_filename,
        output_path=output_path,
        voice_id=voice_id,
        model_id=model_id,
    )
    if show_saved_message:
        print(f"Saved reply audio: {_display_path(output_path)}")

    if playback and shutil.which("ffplay"):
        play(audio_bytes)
    elif playback:
        print("Playback skipped: ffplay not found.")

    return output_path


def main() -> None:
    sample_text = "Բարև, ես փորձնական պատասխան եմ հայերենով։"
    speak_armenian(sample_text)


if __name__ == "__main__":
    main()
