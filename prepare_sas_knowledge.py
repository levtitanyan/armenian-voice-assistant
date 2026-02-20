from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from STT import transcribe_armenian
from sas_knowledge import (
    load_faq_from_excel,
    load_transcripts_from_dir,
    save_knowledge_items,
)

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"}
BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare SAS HR knowledge base from call recordings + FAQ Excel."
    )
    parser.add_argument(
        "--rar",
        type=str,
        default="data/call_records.rar",
        help="Path to call recordings RAR archive.",
    )
    parser.add_argument(
        "--extract-dir",
        type=str,
        default="data/call_recordings",
        help="Where to extract RAR contents.",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=str,
        default="data/transcripts",
        help="Directory to save generated transcript .txt files.",
    )
    parser.add_argument(
        "--faq",
        type=str,
        default=None,
        help="Path to FAQ Excel file (.xlsx).",
    )
    parser.add_argument(
        "--knowledge-out",
        type=str,
        default="data/sas_knowledge.json",
        help="Path for output knowledge JSON.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Transcribe only first N audio files (0 = all).",
    )
    parser.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="Skip audio transcription and only rebuild JSON from existing transcripts.",
    )
    return parser.parse_args()


def extract_rar(rar_path: Path, extract_dir: Path) -> None:
    if not rar_path.exists():
        raise FileNotFoundError(f"RAR file not found: {rar_path}")
    extract_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bsdtar", "-xf", str(rar_path), "-C", str(extract_dir)],
        check=True,
    )


def collect_audio_files(root_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in root_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def sanitize_stem(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
    return safe.strip("_") or "audio"


def transcribe_audio_files(audio_files: list[Path], transcripts_dir: Path, max_files: int = 0) -> None:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    selected = audio_files[:max_files] if max_files > 0 else audio_files
    total = len(selected)
    if total == 0:
        print("No audio files found for transcription.")
        return

    for index, audio_path in enumerate(selected, start=1):
        transcript_name = f"{index:04d}_{sanitize_stem(audio_path.stem)}.txt"
        transcript_path = transcripts_dir / transcript_name
        if transcript_path.exists():
            print(f"[{index}/{total}] Skip existing transcript: {transcript_path.name}")
            continue

        print(f"[{index}/{total}] Transcribing: {audio_path.name}")
        try:
            text = transcribe_armenian(audio_path)
            transcript_path.write_text(text, encoding="utf-8")
            print(f"Saved transcript: {transcript_path.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to transcribe {audio_path.name}: {exc}")


def main() -> None:
    args = parse_args()

    rar_path = Path(args.rar)
    if not rar_path.is_absolute():
        rar_path = BASE_DIR / rar_path
    rar_path = rar_path.resolve()

    extract_dir = Path(args.extract_dir)
    if not extract_dir.is_absolute():
        extract_dir = BASE_DIR / extract_dir
    extract_dir = extract_dir.resolve()

    transcripts_dir = Path(args.transcripts_dir)
    if not transcripts_dir.is_absolute():
        transcripts_dir = BASE_DIR / transcripts_dir
    transcripts_dir = transcripts_dir.resolve()

    knowledge_out = Path(args.knowledge_out)
    if not knowledge_out.is_absolute():
        knowledge_out = BASE_DIR / knowledge_out
    knowledge_out = knowledge_out.resolve()

    faq_path = Path(args.faq) if args.faq else None
    if faq_path and not faq_path.is_absolute():
        faq_path = (BASE_DIR / faq_path).resolve()
    elif faq_path:
        faq_path = faq_path.resolve()

    if not args.skip_transcribe:
        extract_rar(rar_path=rar_path, extract_dir=extract_dir)
        audio_files = collect_audio_files(extract_dir)
        print(f"Found {len(audio_files)} audio files under: {extract_dir}")
        transcribe_audio_files(
            audio_files=audio_files,
            transcripts_dir=transcripts_dir,
            max_files=args.max_files,
        )

    items = load_transcripts_from_dir(transcript_dir=transcripts_dir)
    print(f"Loaded transcript chunks: {len(items)}")

    if faq_path:
        faq_items = load_faq_from_excel(faq_path)
        items.extend(faq_items)
        print(f"Loaded FAQ entries: {len(faq_items)}")

    if not items:
        raise RuntimeError("No knowledge items found. Check recordings/transcripts/FAQ inputs.")

    output_path = save_knowledge_items(items=items, output_path=knowledge_out)
    print(f"Knowledge base saved: {output_path}")


if __name__ == "__main__":
    main()
