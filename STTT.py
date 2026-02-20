import argparse
import json
from datetime import datetime
from pathlib import Path

from STT import VOICE_INPUT_DIR, record_voice_to_wav, transcribe_armenian
from TTS import TTS_OUTPUT_DIR, speak_armenian
from gemini import gemini_answer_armenian

BASE_DIR = Path(__file__).resolve().parent


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
    parser.add_argument(
        "--save-conversation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Save conversation turns to JSONL (use --no-save-conversation to disable).",
    )
    parser.add_argument(
        "--conversation-file",
        type=str,
        default="data/conversations.jsonl",
        help="Conversation JSONL output path (used when --save-conversation is enabled).",
    )
    return parser.parse_args()


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _append_conversation_row(
    output_path: Path,
    recorded_path: Path,
    reply_path: Path,
    user_text: str,
    assistant_text: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "input_audio_path": str(recorded_path),
        "output_audio_path": str(reply_path),
        "user_text": user_text,
        "assistant_text": assistant_text,
    }
    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _next_numeric_index() -> int:
    VOICE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    max_index = 0
    for directory in (VOICE_INPUT_DIR, TTS_OUTPUT_DIR):
        for path in directory.iterdir():
            if not path.is_file():
                continue
            stem = path.stem
            if stem.isdigit():
                max_index = max(max_index, int(stem))
    return max_index + 1


def main() -> None:
    args = parse_args()
    if not args.input_file and not args.output_file:
        index = _next_numeric_index()
        input_file = f"{index:04d}.wav"
        output_file = f"{index:04d}.mp3"
    elif args.input_file and args.output_file:
        input_file = args.input_file
        output_file = args.output_file
    elif args.input_file:
        input_file = args.input_file
        output_file = f"{Path(args.input_file).stem}.mp3"
    else:
        output_file = args.output_file
        input_file = f"{Path(args.output_file).stem}.wav"

    conversation_file = _resolve_project_path(args.conversation_file)

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

    if args.save_conversation:
        _append_conversation_row(
            output_path=conversation_file,
            recorded_path=recorded_path,
            reply_path=reply_path,
            user_text=user_text,
            assistant_text=answer_text,
        )
        print(f"Conversation appended to: {conversation_file}")


if __name__ == "__main__":
    main()
