import argparse
import json
from datetime import datetime
from pathlib import Path

try:
    from .STT import StopConversationRequested, record_voice_to_wav, transcribe_armenian
    from .TTS import speak_armenian
    from .gemini import gemini_answer_armenian
except ImportError:  # pragma: no cover - supports direct script execution
    from STT import StopConversationRequested, record_voice_to_wav, transcribe_armenian
    from TTS import speak_armenian
    from gemini import gemini_answer_armenian

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IO_DIR = PROJECT_ROOT / "io"
CONVERSATION_PREFIX = "Conversation_"
KNOWLEDGE_JSON_FILE = "data/knowledge.json"


def _display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
        return f"{PROJECT_ROOT.name}/{relative.as_posix()}"
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Looping Armenian voice assistant. "
            "Loads data/knowledge.json as knowledge context and keeps listening until you stop."
        )
    )
    return parser.parse_args()


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _next_conversation_directory() -> Path:
    IO_DIR.mkdir(parents=True, exist_ok=True)

    max_index = 0
    for path in IO_DIR.iterdir():
        if not path.is_dir():
            continue
        if not path.name.startswith(CONVERSATION_PREFIX):
            continue
        suffix = path.name[len(CONVERSATION_PREFIX) :]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))

    return IO_DIR / f"{CONVERSATION_PREFIX}{max_index + 1:03d}"


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


def _save_conversation_json(
    conversation_file: Path,
    conversation_dir: Path,
    knowledge_json: Path,
    history: list[dict],
    started_at: datetime,
) -> None:
    conversation_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "conversation_id": conversation_dir.name,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": datetime.now().isoformat(timespec="seconds"),
        "knowledge_json": str(knowledge_json),
        "turn_count": len(history),
        "turns": history,
    }
    conversation_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parse_args()
    knowledge_path = _resolve_project_path(KNOWLEDGE_JSON_FILE)
    knowledge_context = _load_knowledge_context(knowledge_path)
    history: list[dict] = []
    started_at = datetime.now()

    conversation_dir = _next_conversation_directory()
    voice_input_dir = conversation_dir / "voice_input"
    tts_output_dir = conversation_dir / "tts_output"
    conversation_json_file = conversation_dir / "conversation.json"
    voice_input_dir.mkdir(parents=True, exist_ok=True)
    tts_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded knowledge JSON: {_display_path(knowledge_path)}")
    print(f"Conversation folder: {_display_path(conversation_dir)}")
    print("Loop started.")
    print("Press Enter to finish a turn. Press Esc while recording to stop and save conversation.")

    current_index = 1
    try:
        while True:
            input_file = f"{current_index:04d}.wav"
            output_file = f"{current_index:04d}.mp3"
            current_index += 1

            recorded_path = voice_input_dir / input_file
            try:
                record_voice_to_wav(output_path=recorded_path, show_saved_message=False)
            except StopConversationRequested:
                print("Stopping assistant loop.")
                break

            user_text = transcribe_armenian(recorded_path)
            if not user_text:
                print("Empty transcription. Try again.")
                continue
            print(f"Դուք: {user_text}")

            prompt_with_context = _build_prompt(
                user_text=user_text,
                knowledge_context=knowledge_context,
                history=history,
            )
            answer_text = gemini_answer_armenian(prompt_with_context)
            print(f"SAS HR: {answer_text}")

            speak_armenian(
                text=answer_text,
                output_filename=output_file,
                output_path=tts_output_dir / output_file,
                show_saved_message=False,
            )

            history.append(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user_text": user_text,
                    "assistant_text": answer_text,
                    "input_audio_path": f"voice_input/{input_file}",
                    "output_audio_path": f"tts_output/{output_file}",
                }
            )
    except KeyboardInterrupt:
        print("\nStopping assistant loop (Ctrl+C).")
    finally:
        _save_conversation_json(
            conversation_file=conversation_json_file,
            conversation_dir=conversation_dir,
            knowledge_json=knowledge_path,
            history=history,
            started_at=started_at,
        )
        print(f"Conversation saved to: {_display_path(conversation_json_file)}")


if __name__ == "__main__":
    main()
