import argparse
import json
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any

from STT import VOICE_INPUT_DIR, record_voice_to_wav_on_silence, transcribe_armenian
from TTS import speak_armenian
from gemini import gemini_answer_armenian, gemini_answer_armenian_with_knowledge

BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Armenian call assistant: STT -> Gemini -> TTS (multi-turn)."
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Optional input WAV filename template in voice_input/.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Optional output MP3 filename template in tts_output/.",
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
        "--knowledge-file",
        type=str,
        default="data/sas_knowledge.json",
        help="Path to SAS knowledge JSON file.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of knowledge chunks to retrieve for Gemini context.",
    )
    parser.add_argument(
        "--no-knowledge",
        action="store_true",
        help="Disable knowledge retrieval and use base Gemini prompt only.",
    )
    parser.add_argument(
        "--history-file",
        type=str,
        default="data/session_history.json",
        help="Temporary conversation history JSON path.",
    )
    parser.add_argument(
        "--history-turns",
        type=int,
        default=4,
        help="How many previous turns to include as conversation context.",
    )
    parser.add_argument(
        "--keep-history",
        action="store_true",
        help="Keep history JSON after call ends (default is delete).",
    )
    parser.add_argument(
        "--silence-seconds",
        type=float,
        default=1.2,
        help="How long silence must last before finishing a user turn.",
    )
    parser.add_argument(
        "--energy-threshold",
        type=float,
        default=0.012,
        help="Voice activity threshold for speech detection.",
    )
    return parser.parse_args()


def _resolve_project_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _build_turn_filename(
    template: str | None,
    prefix: str,
    extension: str,
    session_id: str,
    turn: int,
) -> str:
    if template:
        base = Path(template)
        suffix = base.suffix or extension
        stem = base.stem if base.suffix else base.name
        if turn == 1:
            return f"{stem}{suffix}"
        return f"{stem}_{turn}{suffix}"
    return f"{prefix}_{session_id}_{turn:03d}{extension}"


def _write_history(history_path: Path, history: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _history_for_prompt(turns: list[dict[str, Any]], max_turns: int) -> str:
    if not turns:
        return ""
    recent = turns[-max(1, max_turns) :]
    lines: list[str] = []
    for turn in recent:
        lines.append(f"Օգտատեր: {turn.get('user_text', '')}")
        lines.append(f"Օգնական: {turn.get('assistant_text', '')}")
    return "\n".join(lines).strip()


def _generate_answer(
    user_text: str,
    args: argparse.Namespace,
    knowledge_path: Path,
    history_turns: list[dict[str, Any]],
) -> str:
    prompt_text = user_text
    history_block = _history_for_prompt(history_turns, args.history_turns)
    if history_block:
        prompt_text = (
            "Զրույցի նախորդ պատմություն՝\n"
            f"{history_block}\n\n"
            f"Ընթացիկ հարց՝ {user_text}"
        )

    if args.no_knowledge:
        return gemini_answer_armenian(prompt_text)

    if knowledge_path.exists():
        return gemini_answer_armenian_with_knowledge(
            user_text=prompt_text,
            knowledge_path=knowledge_path,
            top_k=args.top_k,
        )

    print(f"Knowledge file not found ({knowledge_path}), using base Gemini response.")
    return gemini_answer_armenian(prompt_text)


def _stop_on_enter(stop_event: Event) -> None:
    try:
        input()
        stop_event.set()
    except EOFError:
        pass


def main() -> None:
    args = parse_args()
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    knowledge_path = _resolve_project_path(args.knowledge_file)
    history_path = _resolve_project_path(args.history_file)
    stop_event = Event()

    history: dict[str, Any] = {
        "session_id": session_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "knowledge_file": str(knowledge_path),
        "turns": [],
    }
    _write_history(history_path, history)

    print("Call session started.")
    print("Speak normally. Recording stops automatically when you are silent.")
    print("Press Enter at any time to end the call.")
    Thread(target=_stop_on_enter, args=(stop_event,), daemon=True).start()

    turn = 1
    try:
        while True:
            if stop_event.is_set():
                break

            input_name = _build_turn_filename(
                template=args.input_file,
                prefix="mic",
                extension=".wav",
                session_id=session_id,
                turn=turn,
            )
            output_name = _build_turn_filename(
                template=args.output_file,
                prefix="reply",
                extension=".mp3",
                session_id=session_id,
                turn=turn,
            )

            input_path = VOICE_INPUT_DIR / input_name
            wav_path = record_voice_to_wav_on_silence(
                output_path=input_path,
                silence_seconds=args.silence_seconds,
                energy_threshold=args.energy_threshold,
                stop_event=stop_event,
            )
            if stop_event.is_set():
                break
            if wav_path is None:
                continue

            user_text = transcribe_armenian(wav_path)
            if not user_text:
                print("Empty transcription. Try speaking again.")
                continue

            print(f"You said (Armenian): {user_text}")
            answer_text = _generate_answer(
                user_text=user_text,
                args=args,
                knowledge_path=knowledge_path,
                history_turns=history["turns"],
            )
            print(f"Gemini answer (Armenian): {answer_text}")

            reply_path = speak_armenian(
                text=answer_text,
                output_filename=output_name,
                voice_id=args.voice_id,
                model_id=args.tts_model,
                playback=not args.no_play,
            )

            turn_record = {
                "turn": turn,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "user_audio_path": str(wav_path),
                "user_text": user_text,
                "assistant_text": answer_text,
                "assistant_audio_path": str(reply_path),
            }
            history["turns"].append(turn_record)
            history["last_updated_at"] = datetime.now().isoformat(timespec="seconds")
            _write_history(history_path, history)
            turn += 1
    except KeyboardInterrupt:
        print("\nCall interrupted by user.")
    finally:
        history["ended_at"] = datetime.now().isoformat(timespec="seconds")
        if args.keep_history:
            _write_history(history_path, history)
            print(f"History kept at: {history_path}")
        elif history_path.exists():
            history_path.unlink()
            print(f"History deleted: {history_path}")

    print("Call session ended.")


if __name__ == "__main__":
    main()
