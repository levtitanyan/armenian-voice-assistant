import argparse
import json
from datetime import datetime
from pathlib import Path

from STT import VOICE_INPUT_DIR, record_voice_to_wav, transcribe_armenian
from TTS import TTS_OUTPUT_DIR, speak_armenian
from gemini import gemini_answer_armenian

BASE_DIR = Path(__file__).resolve().parent
CONVERSATION_FILE = BASE_DIR / "data" / "current_session_conversation.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Looping Armenian voice assistant. "
            "Loads one JSON file as knowledge context and keeps listening until you stop."
        )
    )
    parser.add_argument(
        "knowledge_json",
        type=str,
        help="Path to JSON knowledge file (example: data/sas_knowledge.json).",
    )
    return parser.parse_args()


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


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


def _load_knowledge_context(knowledge_path: Path) -> str:
    if not knowledge_path.exists():
        raise FileNotFoundError(f"Knowledge JSON not found: {knowledge_path}")

    with knowledge_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        blocks: list[str] = []
        for idx, item in enumerate(data, start=1):
            if isinstance(item, dict):
                source = str(item.get("source", "unknown"))
                text = str(item.get("text", json.dumps(item, ensure_ascii=False)))
                blocks.append(f"[{idx}] source={source}\n{text}")
            else:
                blocks.append(f"[{idx}]\n{str(item)}")
        if not blocks:
            raise RuntimeError(f"Knowledge JSON list is empty: {knowledge_path}")
        return "\n\n".join(blocks)

    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2)

    return str(data)


def _build_history_block(history: list[dict], max_turns: int = 20) -> str:
    if not history:
        return "(no previous turns yet)"

    recent_turns = history[-max_turns:]
    lines: list[str] = []
    for idx, turn in enumerate(recent_turns, start=1):
        lines.append(
            f"[Turn {idx}] User: {turn['user_text']}\n"
            f"[Turn {idx}] Assistant: {turn['assistant_text']}"
        )
    return "\n".join(lines)


def _build_prompt(
    user_text: str,
    knowledge_context: str,
    history: list[dict],
) -> str:
    history_block = _build_history_block(history)
    return (
        "Use the JSON knowledge below as source context. "
        "Use the CURRENT SESSION conversation history to keep continuity. "
        "If a detail is not present, say that clearly.\n\n"
        f"KNOWLEDGE JSON:\n{knowledge_context}\n\n"
        f"CURRENT SESSION CONVERSATION:\n{history_block}\n\n"
        f"CURRENT USER INPUT:\n{user_text}"
    )


def _append_conversation_row(
    conversation_file: Path,
    knowledge_json: Path,
    recorded_path: Path,
    reply_path: Path,
    user_text: str,
    assistant_text: str,
) -> None:
    conversation_file.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "knowledge_json": str(knowledge_json),
        "input_audio_path": str(recorded_path),
        "output_audio_path": str(reply_path),
        "user_text": user_text,
        "assistant_text": assistant_text,
    }
    with conversation_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    knowledge_path = _resolve_project_path(args.knowledge_json)
    knowledge_context = _load_knowledge_context(knowledge_path)
    history: list[dict] = []
    if CONVERSATION_FILE.exists():
        CONVERSATION_FILE.unlink()

    print(f"Loaded knowledge JSON: {knowledge_path}")
    print(f"Session conversation file: {CONVERSATION_FILE}")
    print("Conversation loop started.")
    print("Speak to start each turn. Stop speaking to end the turn automatically.")
    print("Press Ctrl+C to stop.")

    current_index = _next_numeric_index()
    try:
        while True:
            input_file = f"{current_index:04d}.wav"
            output_file = f"{current_index:04d}.mp3"
            current_index += 1

            recorded_path = VOICE_INPUT_DIR / input_file
            try:
                record_voice_to_wav(recorded_path)
            except RuntimeError as exc:
                print(f"Recording skipped: {exc}")
                continue

            user_text = transcribe_armenian(recorded_path)
            if not user_text:
                print("Empty transcription. Try again.")
                continue
            print(f"You said (Armenian): {user_text}")

            prompt_with_context = _build_prompt(
                user_text=user_text,
                knowledge_context=knowledge_context,
                history=history,
            )
            answer_text = gemini_answer_armenian(prompt_with_context)
            print(f"Gemini answer (Armenian): {answer_text}")

            reply_path = speak_armenian(
                text=answer_text,
                output_filename=output_file,
            )
            print(f"Reply saved to: {reply_path}")

            history.append(
                {
                    "user_text": user_text,
                    "assistant_text": answer_text,
                    "input_audio_path": str(recorded_path),
                    "output_audio_path": str(reply_path),
                }
            )
            _append_conversation_row(
                conversation_file=CONVERSATION_FILE,
                knowledge_json=knowledge_path,
                recorded_path=recorded_path,
                reply_path=reply_path,
                user_text=user_text,
                assistant_text=answer_text,
            )
            print(f"Conversation appended to: {CONVERSATION_FILE}")
    except KeyboardInterrupt:
        print("\nStopping assistant loop (Ctrl+C).")
    finally:
        if CONVERSATION_FILE.exists():
            CONVERSATION_FILE.unlink()
            print(f"Deleted session conversation file: {CONVERSATION_FILE}")


if __name__ == "__main__":
    main()
