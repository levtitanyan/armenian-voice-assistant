"""Main voice assistant loop: STT -> Gemini FAQ match -> fallback generation -> TTS."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

try:
    from .STT import StopConversationRequested, record_voice_to_wav, transcribe_armenian
    from .TTS import play_prebuilt_audio, speak_armenian
    from .common import PROJECT_ROOT, display_path, resolve_project_path
    from .gemini import find_similar_faq_for_question, gemini_answer_armenian
except ImportError:  # pragma: no cover - supports direct script execution
    from STT import StopConversationRequested, record_voice_to_wav, transcribe_armenian
    from TTS import play_prebuilt_audio, speak_armenian
    from common import PROJECT_ROOT, display_path, resolve_project_path
    from gemini import find_similar_faq_for_question, gemini_answer_armenian

CONVERSATIONS_DIR = PROJECT_ROOT / "data" / "conversations"
CONVERSATION_PREFIX = "Conversation_"
DEFAULT_KNOWLEDGE_JSON = "data/knowledge.json"

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for assistant runtime configuration."""
    parser = argparse.ArgumentParser(
        description=(
            "Looping Armenian voice assistant. "
            "Loads data/knowledge.json as generation context and listens until stopped."
        )
    )
    parser.add_argument(
        "--knowledge-json",
        default=DEFAULT_KNOWLEDGE_JSON,
        help=f"Path to knowledge JSON (default: {DEFAULT_KNOWLEDGE_JSON})",
    )
    parser.add_argument(
        "--manual-recording",
        action="store_true",
        help="Use Enter/Esc manual recording mode instead of automatic speech detection.",
    )
    return parser.parse_args()


def _next_conversation_directory() -> Path:
    """Create and return the next numbered conversation directory."""
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    max_index = 0
    for path in CONVERSATIONS_DIR.iterdir():
        if not path.is_dir() or not path.name.startswith(CONVERSATION_PREFIX):
            continue
        suffix = path.name[len(CONVERSATION_PREFIX) :]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))

    return CONVERSATIONS_DIR / f"{CONVERSATION_PREFIX}{max_index + 1:03d}"


def _load_knowledge_context(knowledge_path: Path) -> str:
    """Load knowledge JSON and convert it into a prompt-ready text block."""
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
                blocks.append(f"[{idx}]\n{item}")

        if not blocks:
            raise RuntimeError(f"Knowledge JSON list is empty: {knowledge_path}")
        return "\n\n".join(blocks)

    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2)

    return str(data)


def _build_history_block(history: list[dict], max_turns: int = 20) -> str:
    """Serialize recent turns into a compact prompt history block."""
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


def _build_generation_prompt(user_text: str, knowledge_context: str, history: list[dict]) -> str:
    """Build fallback-generation prompt with knowledge and session context."""
    history_block = _build_history_block(history)
    return (
        "Use the JSON knowledge below as source context. "
        "Use current conversation history for continuity. "
        "If a detail is missing, say that clearly.\n\n"
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
    """Persist session metadata and all turns to `conversation.json`."""
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
    """Run the interactive assistant loop until Esc/interrupt."""
    args = parse_args()
    knowledge_path = resolve_project_path(args.knowledge_json)
    knowledge_context = _load_knowledge_context(knowledge_path)

    history: list[dict] = []
    started_at = datetime.now()

    conversation_dir = _next_conversation_directory()
    voice_input_dir = conversation_dir / "voice_input"
    tts_output_dir = conversation_dir / "tts_output"
    conversation_json_file = conversation_dir / "conversation.json"
    voice_input_dir.mkdir(parents=True, exist_ok=True)
    tts_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded knowledge JSON: {display_path(knowledge_path)}")
    print(f"Conversation folder: {display_path(conversation_dir)}")
    print("Loop started.")
    if args.manual_recording:
        print("Manual mode: Press Enter to finish a turn. Press Esc while recording to stop.")
    else:
        print("Auto mode: start speaking to begin a turn. After assistant audio ends, listening resumes automatically.")
        print("Press Esc while listening/recording to stop and save conversation.")

    current_index = 1
    try:
        while True:
            input_file = f"{current_index:04d}.wav"
            output_file = f"{current_index:04d}.mp3"
            current_index += 1

            recorded_path = voice_input_dir / input_file
            try:
                record_voice_to_wav(
                    output_path=recorded_path,
                    show_saved_message=False,
                    auto_vad=not args.manual_recording,
                )
            except StopConversationRequested:
                print("Stopping assistant loop.")
                break

            user_text = transcribe_armenian(recorded_path)
            if not user_text:
                print("Empty transcription. Try again.")
                continue

            print(f"Դուք: {user_text}")

            response_source = "gemini_generated"
            voice_source = "tts_generated"
            voice_faq_id: int | None = None
            voice_match_score: float | None = None

            faq_match: dict[str, int | str | float | Path] | None
            try:
                faq_match = find_similar_faq_for_question(user_text)
            except Exception as exc:  # noqa: BLE001
                print(f"FAQ match failed; falling back to generation: {exc}")
                faq_match = None

            if faq_match:
                answer_text = str(faq_match.get("faq_answer", "")).strip()
                voice_faq_id = int(faq_match.get("faq_id", 0))
                voice_match_score = float(faq_match.get("score", 0.0))
                response_source = "faq_match"

                if voice_faq_id > 0:
                    print(f"SAS HR (FAQ #{voice_faq_id}): {answer_text}")
                else:
                    print(f"SAS HR (FAQ): {answer_text}")

                matched_voice_path = faq_match.get("voice_path")
                if isinstance(matched_voice_path, Path):
                    play_prebuilt_audio(
                        audio_path=matched_voice_path,
                        output_path=tts_output_dir / output_file,
                        playback=True,
                        show_used_message=True,
                    )
                    voice_source = "faq_prebuilt"
                else:
                    print("Validated pre-recorded FAQ voice not found; generating TTS from FAQ answer.")
                    speak_armenian(
                        text=answer_text,
                        output_filename=output_file,
                        output_path=tts_output_dir / output_file,
                        show_saved_message=False,
                    )
                    voice_source = "tts_generated_from_faq"
            else:
                generation_prompt = _build_generation_prompt(
                    user_text=user_text,
                    knowledge_context=knowledge_context,
                    history=history,
                )
                answer_text = gemini_answer_armenian(generation_prompt)
                print(f"SAS HR: {answer_text}")
                speak_armenian(
                    text=answer_text,
                    output_filename=output_file,
                    output_path=tts_output_dir / output_file,
                    show_saved_message=False,
                )

            turn = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "user_text": user_text,
                "assistant_text": answer_text,
                "response_source": response_source,
                "voice_source": voice_source,
                "input_audio_path": f"voice_input/{input_file}",
                "output_audio_path": f"tts_output/{output_file}",
            }
            if voice_faq_id and voice_faq_id > 0:
                turn["voice_faq_id"] = voice_faq_id
            if voice_match_score is not None:
                turn["voice_match_score"] = voice_match_score

            history.append(turn)
    except KeyboardInterrupt:
        print("\nStopping assistant loop.")
    finally:
        _save_conversation_json(
            conversation_file=conversation_json_file,
            conversation_dir=conversation_dir,
            knowledge_json=knowledge_path,
            history=history,
            started_at=started_at,
        )
        print(f"Conversation saved to: {display_path(conversation_json_file)}")


if __name__ == "__main__":
    main()
