import argparse
import json
from datetime import datetime
from pathlib import Path

try:
    from .TTS import synthesize_armenian_mp3
except ImportError:  # pragma: no cover - supports direct script execution
    from TTS import synthesize_armenian_mp3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAQ_JSON = "data/faq.json"
DEFAULT_OUTPUT_DIR = "data/voice-answers"


def _display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
        return f"{PROJECT_ROOT.name}/{relative.as_posix()}"
    except ValueError:
        return str(path)


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _load_faq_answers(faq_json_path: Path) -> list[dict[str, int | str]]:
    if not faq_json_path.exists():
        raise FileNotFoundError(f"FAQ JSON not found: {faq_json_path}")

    with faq_json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise RuntimeError(
            f"FAQ JSON must contain a list at top-level or in 'items': {faq_json_path}"
        )

    answer_by_id: dict[int, str] = {}
    for fallback_id, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        raw_id = item.get("id", fallback_id)
        try:
            faq_id = int(raw_id)
        except (TypeError, ValueError):
            faq_id = fallback_id

        answer = str(item.get("answer", "")).strip()
        if not answer:
            continue

        existing = answer_by_id.get(faq_id)
        if existing and existing != answer:
            raise RuntimeError(
                f"Duplicate FAQ id with different answers: {faq_id}. "
                "Keep one answer per id for deterministic voice mapping."
            )
        answer_by_id[faq_id] = answer

    answers = [{"id": faq_id, "answer": answer_by_id[faq_id]} for faq_id in sorted(answer_by_id)]
    if not answers:
        raise RuntimeError(f"No valid FAQ answers found in: {faq_json_path}")
    return answers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate MP3 files for FAQ answers from data/faq.json. "
            "One file per answer id (e.g., 001_answer.mp3, 002_answer.mp3)."
        )
    )
    parser.add_argument(
        "--faq-json",
        default=DEFAULT_FAQ_JSON,
        help=f"Path to FAQ JSON file (default: {DEFAULT_FAQ_JSON})",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output folder for generated voice files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate files even if they already exist.",
    )
    parser.add_argument(
        "--voice-id",
        default="JBFqnCBsd6RMkjVDRZzb",
        help="ElevenLabs voice id.",
    )
    parser.add_argument(
        "--model-id",
        default="eleven_v3",
        help="ElevenLabs model id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    faq_json_path = _resolve_project_path(args.faq_json)
    output_dir = _resolve_project_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    answers = _load_faq_answers(faq_json_path)
    max_id = max(int(item["id"]) for item in answers)
    width = max(3, len(str(max_id)))

    created = 0
    skipped = 0
    manifest_items: list[dict[str, int | str]] = []

    for index, item in enumerate(answers, start=1):
        faq_id = int(item["id"])
        answer = str(item["answer"])
        output_filename = f"{faq_id:0{width}d}_answer.mp3"
        output_path = output_dir / output_filename

        if output_path.exists() and not args.overwrite:
            skipped += 1
            status = "skipped"
        else:
            synthesize_armenian_mp3(
                text=answer,
                output_filename=output_filename,
                output_path=output_path,
                voice_id=args.voice_id,
                model_id=args.model_id,
            )
            created += 1
            status = "created"

        print(f"[{index}/{len(answers)}] {status}: FAQ #{faq_id} -> {_display_path(output_path)}")
        manifest_items.append({"id": faq_id, "file": output_filename, "answer": answer})

    manifest_path = output_dir / "index.json"
    manifest_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "faq_json": _display_path(faq_json_path),
        "total_answers": len(answers),
        "created": created,
        "skipped": skipped,
        "items": manifest_items,
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"FAQ JSON: {_display_path(faq_json_path)}")
    print(f"Voice answers folder: {_display_path(output_dir)}")
    print(f"Manifest: {_display_path(manifest_path)}")
    print(f"Created: {created}, Skipped: {skipped}, Total: {len(answers)}")


if __name__ == "__main__":
    main()
