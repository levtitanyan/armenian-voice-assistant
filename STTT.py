import argparse
from datetime import datetime

from STT import VOICE_INPUT_DIR, record_voice_to_wav, transcribe_armenian
from TTS import speak_armenian
from gemini import gemini_answer_armenian


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end Armenian voice assistant: STT -> Gemini -> TTS."
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="WAV filename for microphone recording (saved under voice_input/).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="MP3 filename for assistant reply (saved under tts_output/).",
    )
    parser.add_argument(
        "--voice-id",
        type=str,
        default="JBFqnCBsd6RMkjVDRZzb",
        help="ElevenLabs voice id for generated speech.",
    )
    parser.add_argument(
        "--tts-model",
        type=str,
        default="eleven_v3",
        help="ElevenLabs TTS model id.",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Disable reply audio playback.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_file = args.input_file or f"mic_{timestamp}.wav"
    output_file = args.output_file or f"reply_{timestamp}.mp3"

    recorded_path = VOICE_INPUT_DIR / input_file
    record_voice_to_wav(recorded_path)

    user_text = transcribe_armenian(recorded_path)
    if not user_text:
        raise RuntimeError("Empty transcription; please try recording again.")
    print(f"You said (Armenian): {user_text}")

    answer_text = gemini_answer_armenian(user_text)
    print(f"Gemini answer (Armenian): {answer_text}")

    reply_path = speak_armenian(
        text=answer_text,
        output_filename=output_file,
        voice_id=args.voice_id,
        model_id=args.tts_model,
        playback=not args.no_play,
    )
    print(f"Reply saved to: {reply_path}")


if __name__ == "__main__":
    main()
