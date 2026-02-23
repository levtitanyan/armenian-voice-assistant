import os
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

BASE_DIR = Path(__file__).resolve().parent
VOICE_INPUT_DIR = BASE_DIR / "voice_input"
SAMPLE_RATE = 16000


def _get_elevenlabs_client() -> ElevenLabs:
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def _rms(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(signal))))


def record_voice_to_wav(
    output_path: Path,
    sample_rate: int = SAMPLE_RATE,
    chunk_duration: float = 0.1,
    speech_threshold: float = 0.015,
    start_timeout_s: float = 10.0,
    silence_duration_s: float = 1.0,
    max_duration_s: float = 20.0,
) -> Path:
    VOICE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_size = int(sample_rate * chunk_duration)
    start_time = time.monotonic()
    speaking_started = False
    silence_elapsed = 0.0
    speech_elapsed = 0.0
    frames: list[np.ndarray] = []

    print("Listening... start speaking.")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        while True:
            chunk, overflowed = stream.read(chunk_size)
            if overflowed:
                print("Warning: audio buffer overflow detected.")

            energy = _rms(chunk)
            is_speech = energy >= speech_threshold

            if not speaking_started:
                if is_speech:
                    speaking_started = True
                    frames.append(chunk.copy())
                    speech_elapsed = chunk_duration
                    silence_elapsed = 0.0
                    print("Speech detected. Recording...")
                    continue

                if time.monotonic() - start_time >= start_timeout_s:
                    raise RuntimeError(
                        "No speech detected before timeout. Please try again and speak clearly."
                    )
                continue

            frames.append(chunk.copy())
            speech_elapsed += chunk_duration

            if is_speech:
                silence_elapsed = 0.0
            else:
                silence_elapsed += chunk_duration

            if silence_elapsed >= silence_duration_s:
                break
            if speech_elapsed >= max_duration_s:
                print("Reached max recording duration for one turn.")
                break

    if not frames:
        raise RuntimeError("No audio captured from microphone.")

    audio_np = np.concatenate(frames, axis=0)
    sf.write(output_path.as_posix(), audio_np, sample_rate, subtype="PCM_16")
    print(f"Saved voice recording: {output_path}")
    return output_path


def transcribe_armenian(audio_path: Path, model_id: str = "scribe_v2") -> str:
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
    return text.strip()


def record_and_transcribe_armenian(filename: str = "mic.wav") -> tuple[Path, str]:
    output_path = VOICE_INPUT_DIR / filename
    wav_path = record_voice_to_wav(output_path=output_path)
    transcript = transcribe_armenian(wav_path)
    return wav_path, transcript


def main() -> None:
    wav_path, transcript = record_and_transcribe_armenian()
    print(f"Transcription from {wav_path}:")
    print(transcript)


if __name__ == "__main__":
    main()
