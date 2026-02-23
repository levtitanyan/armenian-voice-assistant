import hashlib
import json
import os
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TTS_OUTPUT_DIR = PROJECT_ROOT / "data" / "conversations" / "tts_output"
VOICE_CACHE_DIR = PROJECT_ROOT / "data" / "conversations" / "_voice_cache"
VOICE_CACHE_INDEX = "index.json"
PREBUILT_VOICE_DIR = PROJECT_ROOT / "data" / "voice-answers"
PREBUILT_FAQ_JSON = PROJECT_ROOT / "data" / "faq.json"


def _display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
        return f"{PROJECT_ROOT.name}/{relative.as_posix()}"
    except ValueError:
        return str(path)


def _get_elevenlabs_client() -> ElevenLabs:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY (or XI_API_KEY) in environment or .env file.")
    return ElevenLabs(api_key=api_key)


def _normalize_for_cache(text: str) -> str:
    return " ".join(text.lower().split())


def _normalize_for_similarity(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^\wԱ-Ֆա-ֆЁё\s]", " ", lowered)
    return " ".join(lowered.split())


def _answer_variants(answer: str) -> list[str]:
    variants: list[str] = []
    stripped = answer.strip()
    if stripped:
        variants.append(stripped)

    # Add first sentence variant so short Gemini replies like "Բարև Ձեզ։"
    # can still match a longer FAQ answer.
    first_sentence = re.split(r"[.!?։]\s*", stripped, maxsplit=1)[0].strip()
    if first_sentence and first_sentence not in variants:
        variants.append(first_sentence)

    return variants


def _faq_id_from_voice_filename(path: Path) -> int | None:
    match = re.match(r"^(\d+)_answer\.mp3$", path.name)
    if not match:
        return None
    return int(match.group(1))


def _cache_key(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _load_cache_index(cache_dir: Path) -> dict[str, dict[str, str]]:
    index_path = cache_dir / VOICE_CACHE_INDEX
    if not index_path.exists():
        return {}
    try:
        raw = index_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                str(k): v
                for k, v in data.items()
                if isinstance(v, dict)
                and isinstance(v.get("text"), str)
                and isinstance(v.get("file"), str)
            }
    except Exception:  # noqa: BLE001
        return {}
    return {}


def _save_cache_index(cache_dir: Path, index_data: dict[str, dict[str, str]]) -> None:
    (cache_dir / VOICE_CACHE_INDEX).write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_prebuilt_voice_catalog(
    voice_answers_dir: Path | None,
    faq_json_path: Path | None,
) -> list[dict[str, int | str | Path | list[dict[str, str | set[str]]]]]:
    if voice_answers_dir is None or faq_json_path is None:
        return []
    if not voice_answers_dir.exists() or not faq_json_path.exists():
        return []

    try:
        payload = json.loads(faq_json_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []

    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return []

    entries: list[dict[str, int | str | Path | list[dict[str, str | set[str]]]]] = []
    for fallback_id, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        raw_id = item.get("id", fallback_id)
        try:
            faq_id = int(raw_id)
        except (TypeError, ValueError):
            faq_id = fallback_id

        voice_file_value = item.get("voice_file")
        if isinstance(voice_file_value, str) and voice_file_value.strip():
            voice_filename = voice_file_value.strip()
        else:
            # Deterministic mapping: FAQ id -> {id:03d}_answer.mp3
            voice_filename = f"{faq_id:03d}_answer.mp3"

        audio_path = voice_answers_dir / voice_filename
        if not audio_path.exists():
            continue

        answer = str(item.get("answer", "")).strip()
        variants = _answer_variants(answer)
        norm_variants: list[dict[str, str | set[str]]] = []
        for variant in variants:
            norm_variant = _normalize_for_similarity(variant)
            if not norm_variant:
                continue
            norm_variants.append(
                {
                    "norm_text": norm_variant,
                    "tokens": set(norm_variant.split()),
                }
            )

        if not norm_variants:
            continue

        entries.append(
            {
                "id": faq_id,
                "answer": answer,
                "audio_path": audio_path,
                "norm_variants": norm_variants,
            }
        )

    return entries


def _find_prebuilt_faq_audio(
    text: str,
    voice_answers_dir: Path | None,
    faq_json_path: Path | None,
    similarity_threshold: float,
) -> Path | None:
    catalog = _load_prebuilt_voice_catalog(
        voice_answers_dir=voice_answers_dir,
        faq_json_path=faq_json_path,
    )
    if not catalog:
        return None

    normalized = _normalize_for_similarity(text)
    if not normalized:
        return None

    user_tokens = set(normalized.split())
    best_score = 0.0
    best_path: Path | None = None

    for item in catalog:
        norm_variants = item.get("norm_variants")
        if not isinstance(norm_variants, list):
            continue

        item_best_score = 0.0
        for variant in norm_variants:
            if not isinstance(variant, dict):
                continue

            norm_answer = str(variant.get("norm_text", ""))
            if not norm_answer:
                continue
            answer_tokens = variant.get("tokens")
            if not isinstance(answer_tokens, set):
                answer_tokens = set()

            ratio = SequenceMatcher(None, normalized, norm_answer).ratio()
            token_overlap = 0.0
            jaccard = 0.0
            if answer_tokens:
                intersection = len(user_tokens & answer_tokens)
                token_overlap = intersection / max(1, min(len(user_tokens), len(answer_tokens)))
                jaccard = intersection / max(1, len(user_tokens | answer_tokens))

            substring_bonus = 0.0
            if norm_answer in normalized or normalized in norm_answer:
                substring_bonus = 0.12

            score = (0.55 * ratio) + (0.35 * token_overlap) + (0.10 * jaccard) + substring_bonus
            if score > item_best_score:
                item_best_score = score

        if item_best_score > best_score:
            best_score = item_best_score
            candidate_path = item.get("audio_path")
            if isinstance(candidate_path, Path):
                best_path = candidate_path

    if best_path is not None and best_score >= similarity_threshold:
        return best_path
    return None


def _find_cached_audio(
    text: str,
    cache_dir: Path | None,
    similarity_threshold: float,
) -> Path | None:
    if cache_dir is None:
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_for_cache(text)
    key = _cache_key(normalized)
    exact_path = cache_dir / f"{key}.mp3"
    if exact_path.exists():
        return exact_path

    index_data = _load_cache_index(cache_dir)
    best_ratio = 0.0
    best_file: str | None = None

    for _, meta in index_data.items():
        cached_text = meta.get("text", "")
        cached_file = meta.get("file", "")
        if not cached_text or not cached_file:
            continue
        ratio = SequenceMatcher(None, normalized, cached_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_file = cached_file

    if best_file and best_ratio >= similarity_threshold:
        candidate = cache_dir / best_file
        if candidate.exists():
            return candidate
    return None


def _store_audio_in_cache(text: str, audio_bytes: bytes, cache_dir: Path | None) -> None:
    if cache_dir is None:
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_for_cache(text)
    key = _cache_key(normalized)
    cache_file = cache_dir / f"{key}.mp3"
    if not cache_file.exists():
        cache_file.write_bytes(audio_bytes)

    index_data = _load_cache_index(cache_dir)
    index_data[key] = {"text": normalized, "file": cache_file.name}
    _save_cache_index(cache_dir, index_data)


def synthesize_armenian_mp3(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
) -> tuple[Path, bytes]:
    if output_path is None:
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = TTS_OUTPUT_DIR / output_filename
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    client = _get_elevenlabs_client()
    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format="mp3_44100_128",
        language_code="hy",
    )
    audio_bytes = b"".join(audio_stream)
    output_path.write_bytes(audio_bytes)
    return output_path, audio_bytes


def speak_armenian(
    text: str,
    output_filename: str = "armenian_tts.mp3",
    output_path: Path | None = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_v3",
    playback: bool = True,
    show_saved_message: bool = False,
    prebuilt_voice_dir: Path | None = PREBUILT_VOICE_DIR,
    prebuilt_faq_json_path: Path | None = PREBUILT_FAQ_JSON,
    prebuilt_similarity_threshold: float = 0.4,
    cache_dir: Path | None = VOICE_CACHE_DIR,
    similarity_threshold: float = 0.4,
) -> Path:
    if output_path is None:
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = TTS_OUTPUT_DIR / output_filename
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    prebuilt_audio_path = _find_prebuilt_faq_audio(
        text=text,
        voice_answers_dir=prebuilt_voice_dir,
        faq_json_path=prebuilt_faq_json_path,
        similarity_threshold=prebuilt_similarity_threshold,
    )

    if prebuilt_audio_path is not None:
        if prebuilt_audio_path.resolve() != output_path.resolve():
            shutil.copyfile(prebuilt_audio_path, output_path)
        audio_bytes = output_path.read_bytes()
        prebuilt_id = _faq_id_from_voice_filename(prebuilt_audio_path)
        if prebuilt_id is not None:
            print(
                "Used pre-recorded FAQ voice "
                f"(id={prebuilt_id}): {_display_path(prebuilt_audio_path)}"
            )
        else:
            print(f"Used pre-recorded FAQ voice: {_display_path(prebuilt_audio_path)}")
        _store_audio_in_cache(text=text, audio_bytes=audio_bytes, cache_dir=cache_dir)
    else:
        cached_audio_path = _find_cached_audio(
            text=text,
            cache_dir=cache_dir,
            similarity_threshold=similarity_threshold,
        )

        if cached_audio_path is not None:
            if cached_audio_path.resolve() != output_path.resolve():
                shutil.copyfile(cached_audio_path, output_path)
            audio_bytes = output_path.read_bytes()
        else:
            output_path, audio_bytes = synthesize_armenian_mp3(
                text=text,
                output_filename=output_filename,
                output_path=output_path,
                voice_id=voice_id,
                model_id=model_id,
            )
            _store_audio_in_cache(text=text, audio_bytes=audio_bytes, cache_dir=cache_dir)

    if show_saved_message:
        print(f"Saved reply audio: {_display_path(output_path)}")

    if playback and shutil.which("ffplay"):
        play(audio_bytes)
    elif playback:
        print("Playback skipped: ffplay not found.")

    return output_path


def main() -> None:
    sample_text = "Բարև, ես փորձնական պատասխան եմ հայերենով։"
    speak_armenian(sample_text)


if __name__ == "__main__":
    main()
