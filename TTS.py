import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

BASE_DIR = Path(__file__).resolve().parent
TTS_OUTPUT_DIR = BASE_DIR / "tts_output"


def _get_elevenlabs_client() -> ElevenLabs:
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def synthesize_armenian_mp3(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
) -> tuple[Path, bytes]:
    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TTS_OUTPUT_DIR / output_filename

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
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
    playback: bool = True,
) -> Path:
    output_path, audio_bytes = synthesize_armenian_mp3(
        text=text,
        output_filename=output_filename,
        voice_id=voice_id,
        model_id=model_id,
    )
    print(f"Saved reply audio: {output_path}")

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
