import argparse
import json
from pathlib import Path

try:
    from .STT import transcribe_armenian
except ImportError:  # pragma: no cover - supports direct script execution
    from STT import transcribe_armenian

AUDIO_EXTENSIONS = {".wav", ".m4a", ".mp3", ".ogg", ".flac", ".aac"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe audio files and append them to a JSONL dataset."
    )
    parser.add_argument(
        "--audio-dir",
        type=str,
        default="data/call_recordings",
        help="Directory containing source audio files.",
    )
    parser.add_argument(
        "--dataset-out",
        type=str,
        default="data/sas_dataset.jsonl",
        help="Output JSONL dataset path.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Limit to N files from the selected start index (0 = all).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index in sorted audio list to start from.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip audio paths that already exist in dataset-out.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite dataset-out instead of appending.",
    )
    return parser.parse_args()


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def collect_audio_files(audio_dir: Path) -> list[Path]:
    if not audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")
    files = [
        path
        for path in audio_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


def load_existing_audio_paths(dataset_out: Path) -> set[str]:
    existing: set[str] = set()
    if not dataset_out.exists():
        return existing
    for line in dataset_out.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        audio_path = row.get("audio_path")
        if isinstance(audio_path, str):
            existing.add(audio_path)
    return existing


def main() -> None:
    args = parse_args()
    audio_dir = resolve_path(args.audio_dir)
    dataset_out = resolve_path(args.dataset_out)

    audio_files = collect_audio_files(audio_dir)
    if args.start_index < 0:
        raise ValueError("--start-index must be >= 0")
    audio_files = audio_files[args.start_index :]
    if args.max_files > 0:
        audio_files = audio_files[: args.max_files]

    existing = load_existing_audio_paths(dataset_out) if args.skip_existing else set()
    mode = "w" if args.overwrite else "a"
    dataset_out.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    failed = 0
    with dataset_out.open(mode, encoding="utf-8") as output:
        for index, audio_path in enumerate(audio_files, start=1):
            audio_abs = str(audio_path.resolve())
            if audio_abs in existing:
                skipped += 1
                continue

            print(f"[{index}/{len(audio_files)}] Transcribing: {audio_path.name}")
            try:
                transcript = transcribe_armenian(audio_path)
            except Exception as exc:  # noqa: BLE001
                print(f"Failed: {audio_path.name} -> {exc}")
                failed += 1
                continue

            global_index = args.start_index + index
            row = {
                "id": f"sample-{global_index:05d}",
                "audio_path": audio_abs,
                "transcript": transcript,
            }
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1

    print(f"Dataset file: {dataset_out}")
    print(f"Written: {written}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    main()
