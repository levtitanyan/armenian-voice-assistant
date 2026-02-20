import os
from collections import deque
from pathlib import Path
from threading import Event

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


def record_voice_to_wav(output_path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    VOICE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []

    def callback(indata, frames_count, time_info, status) -> None:  # type: ignore[no-untyped-def]
        if status:
            print(status)
        frames.append(indata.copy())

    print("Recording... press Enter to stop.")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", callback=callback):
        input()

    if not frames:
        raise RuntimeError("No audio captured from microphone.")

    audio_np = np.concatenate(frames, axis=0)
    sf.write(output_path.as_posix(), audio_np, sample_rate, subtype="PCM_16")
    print(f"Saved voice recording: {output_path}")
    return output_path


def record_voice_to_wav_on_silence(
    output_path: Path,
    sample_rate: int = SAMPLE_RATE,
    chunk_seconds: float = 0.1,
    silence_seconds: float = 1.2,
    min_speech_seconds: float = 0.3,
    pre_speech_seconds: float = 0.4,
    energy_threshold: float = 0.012,
    stop_event: Event | None = None,
) -> Path | None:
    VOICE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames_per_chunk = max(1, int(sample_rate * chunk_seconds))
    silence_chunks_to_stop = max(1, int(silence_seconds / chunk_seconds))
    min_speech_chunks = max(1, int(min_speech_seconds / chunk_seconds))
    pre_buffer_chunks = max(1, int(pre_speech_seconds / chunk_seconds))

    pre_buffer: deque[np.ndarray] = deque(maxlen=pre_buffer_chunks)
    captured_chunks: list[np.ndarray] = []
    speech_started = False
    speech_chunks = 0
    silent_chunks = 0

    print("Listening... (speak normally; auto-stop on silence)")
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=frames_per_chunk,
    ) as stream:
        while True:
            if stop_event and stop_event.is_set():
                return None

            chunk, overflowed = stream.read(frames_per_chunk)
            if overflowed:
                print("Audio overflow detected.")

            frame = chunk.copy()
            rms = float(np.sqrt(np.mean(np.square(frame))))
            is_speech = rms >= energy_threshold

            if not speech_started:
                pre_buffer.append(frame)
                if is_speech:
                    speech_started = True
                    captured_chunks.extend(pre_buffer)
                    pre_buffer.clear()
                    speech_chunks += 1
                continue

            captured_chunks.append(frame)
            if is_speech:
                speech_chunks += 1
                silent_chunks = 0
            else:
                silent_chunks += 1
                if speech_chunks >= min_speech_chunks and silent_chunks >= silence_chunks_to_stop:
                    break

    if speech_chunks < min_speech_chunks or not captured_chunks:
        return None

    audio_np = np.concatenate(captured_chunks, axis=0)
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
