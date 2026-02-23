"""Build `data/knowledge.json` from call recordings and transcript files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .STT import transcribe_armenian
    from .common import display_path, resolve_project_path
except ImportError:  # pragma: no cover - supports direct script execution
    from STT import transcribe_armenian
    from common import display_path, resolve_project_path

AUDIO_EXTENSIONS = {".wav", ".m4a", ".mp3", ".ogg", ".flac", ".aac", ".mp4"}
CALL_KEY_PATTERN = re.compile(r"(\d{6,})_(\d{6})_(\d{6})")
TRANSCRIPT_PREFIX_PATTERN = re.compile(r"^(\d+)_")
DEFAULT_SOURCE_TYPE = "call_recording_transcript"
DEFAULT_AUDIO_DIR = "data/call_records"
DEFAULT_TRANSCRIPTS_DIR = "data/transcripts"
DEFAULT_KNOWLEDGE_JSON = "data/knowledge.json"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for dataset build range selection."""
    parser = argparse.ArgumentParser(
        description=(
            "Build data/knowledge.json from data/call_records and data/transcripts. "
            "Reuses existing TXT transcripts, transcribes only missing ones."
        )
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Limit to N files from selected start index (0 = all).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index in sorted audio list to start from.",
    )
    return parser.parse_args()


def collect_audio_files(audio_dir: Path) -> list[Path]:
    """Collect all supported audio files recursively, sorted by path."""
    if not audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

    files = [
        path
        for path in audio_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


def extract_call_key(filename: str) -> str | None:
    """Extract a stable call key from filename when pattern matches."""
    match = CALL_KEY_PATTERN.search(filename)
    if not match:
        return None
    return "_".join(match.groups())


def normalize_stem(name: str) -> str:
    """Normalize base filename for transcript naming consistency."""
    return re.sub(r"\s+", "_", name.strip())


def load_knowledge_items(knowledge_json: Path, overwrite: bool) -> list[dict]:
    """Load existing knowledge items unless overwrite is enabled."""
    if overwrite or not knowledge_json.exists():
        return []

    raw = knowledge_json.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    data = json.loads(raw)
    if not isinstance(data, list):
        raise RuntimeError(f"Knowledge JSON must be a list: {knowledge_json}")

    return [item for item in data if isinstance(item, dict)]


def existing_audio_paths(items: list[dict]) -> set[str]:
    """Return absolute audio paths already present in knowledge items."""
    paths: set[str] = set()
    for item in items:
        audio_path = None

        meta = item.get("meta")
        if isinstance(meta, dict):
            candidate = meta.get("audio_path")
            if isinstance(candidate, str):
                audio_path = candidate

        if audio_path is None:
            candidate = item.get("audio_path")
            if isinstance(candidate, str):
                audio_path = candidate

        if audio_path:
            paths.add(str(Path(audio_path).resolve()))

    return paths


def next_item_number(items: list[dict]) -> int:
    """Find next incremental numeric suffix for new knowledge items."""
    max_num = 0
    for item in items:
        for key in ("item_id", "id"):
            raw = str(item.get(key, ""))
            match = re.search(r"(\d+)$", raw)
            if match:
                max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def build_transcript_key_index(transcripts_dir: Path) -> dict[str, Path]:
    """Index existing transcript files by extracted call key."""
    index: dict[str, Path] = {}
    if not transcripts_dir.exists():
        return index

    for path in sorted(transcripts_dir.glob("*.txt")):
        key = extract_call_key(path.name)
        if key and key not in index:
            index[key] = path.resolve()
    return index


def find_transcript_for_audio(
    audio_path: Path,
    transcripts_dir: Path,
    transcript_key_index: dict[str, Path],
) -> Path | None:
    """Find matching transcript by call key or normalized file stem."""
    key = extract_call_key(audio_path.name)
    if key and key in transcript_key_index:
        return transcript_key_index[key]

    normalized = normalize_stem(audio_path.stem)
    candidates = [
        transcripts_dir / f"{audio_path.stem}.txt",
        transcripts_dir / f"{normalized}.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return None


def next_transcript_number(transcripts_dir: Path) -> int:
    """Get next numeric prefix for newly generated transcript files."""
    max_num = 0
    if not transcripts_dir.exists():
        return 1

    for path in transcripts_dir.glob("*.txt"):
        match = TRANSCRIPT_PREFIX_PATTERN.match(path.name)
        if not match:
            continue
        max_num = max(max_num, int(match.group(1)))

    return max_num + 1


def create_transcript_path(audio_path: Path, transcripts_dir: Path, next_num: int) -> tuple[Path, int]:
    """Create a unique transcript path and return updated counter."""
    base = normalize_stem(audio_path.stem)
    candidate = transcripts_dir / f"{next_num:04d}_{base}.txt"

    while candidate.exists():
        next_num += 1
        candidate = transcripts_dir / f"{next_num:04d}_{base}.txt"

    return candidate, next_num + 1


def read_transcript(path: Path) -> str:
    """Read transcript text from file and trim surrounding whitespace."""
    return path.read_text(encoding="utf-8").strip()


def main() -> None:
    """Build or extend `knowledge.json` from call recordings."""
    args = parse_args()

    audio_dir = resolve_project_path(DEFAULT_AUDIO_DIR)
    transcripts_dir = resolve_project_path(DEFAULT_TRANSCRIPTS_DIR)
    knowledge_json = resolve_project_path(DEFAULT_KNOWLEDGE_JSON)

    transcripts_dir.mkdir(parents=True, exist_ok=True)
    knowledge_json.parent.mkdir(parents=True, exist_ok=True)

    items = load_knowledge_items(knowledge_json=knowledge_json, overwrite=False)
    existing = existing_audio_paths(items)
    next_id = next_item_number(items)

    audio_files = collect_audio_files(audio_dir)
    if args.start_index < 0:
        raise ValueError("--start-index must be >= 0")

    audio_files = audio_files[args.start_index :]
    if args.max_files > 0:
        audio_files = audio_files[: args.max_files]

    transcript_key_index = build_transcript_key_index(transcripts_dir)
    transcript_counter = next_transcript_number(transcripts_dir)

    reused_txt = 0
    created_txt = 0
    written = 0
    skipped = 0
    failed = 0

    for index, audio_path in enumerate(audio_files, start=1):
        audio_abs = str(audio_path.resolve())
        if audio_abs in existing:
            skipped += 1
            continue

        transcript_path = find_transcript_for_audio(
            audio_path=audio_path,
            transcripts_dir=transcripts_dir,
            transcript_key_index=transcript_key_index,
        )
        transcript_text = ""

        if transcript_path and transcript_path.exists():
            transcript_text = read_transcript(transcript_path)
            if transcript_text:
                reused_txt += 1
            else:
                transcript_path = None

        if transcript_path is None:
            print(f"[{index}/{len(audio_files)}] Transcribing: {audio_path.name}")
            try:
                transcript_text = transcribe_armenian(audio_path)
            except Exception as exc:  # noqa: BLE001
                print(f"Failed: {audio_path.name} -> {exc}")
                failed += 1
                continue

            transcript_path, transcript_counter = create_transcript_path(
                audio_path=audio_path,
                transcripts_dir=transcripts_dir,
                next_num=transcript_counter,
            )
            transcript_path.write_text(transcript_text.strip() + "\n", encoding="utf-8")

            key = extract_call_key(audio_path.name)
            if key:
                transcript_key_index[key] = transcript_path.resolve()

            created_txt += 1

        item = {
            "item_id": f"audio-{next_id:05d}",
            "source_type": DEFAULT_SOURCE_TYPE,
            "source": audio_path.name,
            "text": transcript_text.strip(),
            "meta": {
                "audio_path": audio_abs,
                "transcript_path": str(transcript_path.resolve()),
            },
        }
        items.append(item)
        next_id += 1
        written += 1
        existing.add(audio_abs)

    knowledge_json.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Audio folder: {display_path(audio_dir)}")
    print(f"Transcripts folder: {display_path(transcripts_dir)}")
    print(f"Knowledge JSON: {display_path(knowledge_json)}")
    print(f"Written JSON items: {written}, Skipped: {skipped}, Failed: {failed}")
    print(f"Reused TXT: {reused_txt}, Created TXT: {created_txt}")


if __name__ == "__main__":
    main()
