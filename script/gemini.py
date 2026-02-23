"""Gemini integrations for FAQ matching and Armenian answer generation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

try:
    from .common import PROJECT_ROOT, is_mostly_armenian, normalize_for_similarity
except ImportError:  # pragma: no cover - supports direct script execution
    from common import PROJECT_ROOT, is_mostly_armenian, normalize_for_similarity

FAQ_JSON_PATH = PROJECT_ROOT / "data" / "faq.json"
VOICE_ANSWERS_DIR = PROJECT_ROOT / "data" / "voice-answers"
VOICE_ANSWERS_INDEX = "index.json"
FAQ_MATCH_CONFIDENCE_THRESHOLD = 0.72
FAQ_MATCH_MODEL = "gemini-2.5-flash"
ANSWER_MODEL = "gemini-2.5-flash"


def _get_gemini_client() -> genai.Client:
    """Create a Gemini client from `.env`/environment variables."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")
    return genai.Client(api_key=api_key)


def _extract_user_input(raw_text: str) -> str:
    """Extract the plain user input when prompt wrappers are present."""
    markers = ("CURRENT USER INPUT:", "Հարց/մուտք՝", "ՀԱՐՑ/ՄՈՒՏՔ՝")
    for marker in markers:
        if marker in raw_text:
            return raw_text.rsplit(marker, maxsplit=1)[-1].strip()
    return raw_text.strip()


def _extract_first_json_object(text: str) -> str | None:
    """Extract the first complete JSON object substring from free text."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _to_float(value: object, default: float = 0.0) -> float:
    """Parse a float-like value safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: object) -> bool:
    """Parse a bool-like value safely."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _load_faq_catalog(
    faq_json_path: Path,
    voice_answers_dir: Path,
) -> dict[int, dict[str, int | str | Path | None | list[str]]]:
    """Load FAQ items keyed by id with normalized question variants."""
    manifest = _load_voice_answers_manifest(voice_answers_dir)

    if not faq_json_path.exists():
        return {}

    try:
        payload = json.loads(faq_json_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}

    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return {}

    catalog: dict[int, dict[str, int | str | Path | None | list[str]]] = {}

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

        raw_questions = item.get("questions", [])
        questions: list[str] = []
        if isinstance(raw_questions, str):
            question = raw_questions.strip()
            if question:
                questions.append(question)
        elif isinstance(raw_questions, list):
            for question in raw_questions:
                clean = str(question).strip()
                if clean:
                    questions.append(clean)

        if not questions:
            fallback_question = str(item.get("question", "")).strip()
            if fallback_question:
                questions.append(fallback_question)

        if not questions:
            continue

        voice_file_value = item.get("voice_file")
        if isinstance(voice_file_value, str) and voice_file_value.strip():
            voice_filename = voice_file_value.strip()
        else:
            voice_filename = f"{faq_id:03d}_answer.mp3"

        voice_path = _resolve_validated_voice_path(
            faq_id=faq_id,
            faq_answer=answer,
            fallback_filename=voice_filename,
            voice_answers_dir=voice_answers_dir,
            manifest=manifest,
        )

        catalog[faq_id] = {
            "id": faq_id,
            "answer": answer,
            "questions": questions,
            "voice_path": voice_path,
        }

    return catalog


def _load_voice_answers_manifest(voice_answers_dir: Path) -> dict[int, dict[str, str]]:
    """Load voice manifest mapping `faq_id -> {answer, file}`."""
    manifest_path = voice_answers_dir / VOICE_ANSWERS_INDEX
    if not manifest_path.exists():
        return {}

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}

    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return {}

    mapping: dict[int, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue

        try:
            faq_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        answer = str(item.get("answer", "")).strip()
        file_name = str(item.get("file", "")).strip()
        if not answer or not file_name:
            continue

        mapping[faq_id] = {"answer": answer, "file": file_name}

    return mapping


def _resolve_validated_voice_path(
    faq_id: int,
    faq_answer: str,
    fallback_filename: str,
    voice_answers_dir: Path,
    manifest: dict[int, dict[str, str]],
) -> Path | None:
    """Return prebuilt voice path only when manifest answer matches current FAQ answer."""
    manifest_item = manifest.get(faq_id)
    if manifest_item:
        manifest_answer = manifest_item.get("answer", "").strip()
        manifest_file = manifest_item.get("file", "").strip()
        if manifest_answer != faq_answer or not manifest_file:
            return None

        manifest_voice_path = voice_answers_dir / manifest_file
        if manifest_voice_path.exists():
            return manifest_voice_path
        return None

    fallback_path = voice_answers_dir / fallback_filename
    if fallback_path.exists():
        # Without manifest validation we cannot guarantee file-to-answer correctness.
        return None

    return None


def _build_faq_match_prompt(user_question: str, faq_catalog: list[dict[str, object]]) -> str:
    """Build a strict JSON-output prompt for FAQ semantic matching."""
    faq_json_block = json.dumps(faq_catalog, ensure_ascii=False, indent=2)
    return (
        "You are an FAQ matcher. Compare USER_QUESTION with FAQ questions and return JSON only.\n"
        "Return one JSON object with this exact schema:\n"
        '{"matched": true|false, "faq_id": number|null, "confidence": number, '
        '"matched_question": string}\n\n'
        "Rules:\n"
        "1) Set matched=true only if intent is clearly the same.\n"
        "2) If not sure, set matched=false and faq_id=null.\n"
        "3) confidence must be between 0 and 1.\n"
        "4) Never invent FAQ ids.\n\n"
        f"USER_QUESTION:\n{user_question}\n\n"
        f"FAQ_QUESTIONS_JSON:\n{faq_json_block}\n"
    )


def _parse_faq_match_response(response_text: str) -> dict[str, object] | None:
    """Parse and validate FAQ matcher JSON output."""
    payload_text = _extract_first_json_object(response_text)
    if not payload_text:
        return None

    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    matched = _to_bool(parsed.get("matched"))
    faq_id_value = parsed.get("faq_id")
    faq_id: int | None
    if faq_id_value in (None, ""):
        faq_id = None
    else:
        try:
            faq_id = int(faq_id_value)
        except (TypeError, ValueError):
            faq_id = None

    confidence = _to_float(parsed.get("confidence"), default=0.0)
    confidence = max(0.0, min(confidence, 1.0))
    matched_question = str(parsed.get("matched_question", "")).strip()

    return {
        "matched": matched,
        "faq_id": faq_id,
        "confidence": confidence,
        "matched_question": matched_question,
    }


def find_similar_faq_for_question(
    question_text: str,
    similarity_threshold: float = FAQ_MATCH_CONFIDENCE_THRESHOLD,
    faq_json_path: Path = FAQ_JSON_PATH,
    voice_answers_dir: Path = VOICE_ANSWERS_DIR,
    model: str = FAQ_MATCH_MODEL,
) -> dict[str, int | str | float | Path] | None:
    """Use Gemini to find a semantically similar FAQ question and return its answer."""
    normalized = normalize_for_similarity(question_text)
    if not normalized:
        return None

    catalog = _load_faq_catalog(
        faq_json_path=faq_json_path,
        voice_answers_dir=voice_answers_dir,
    )
    if not catalog:
        return None

    faq_catalog_for_prompt = [
        {"id": faq_id, "questions": item.get("questions", [])}
        for faq_id, item in sorted(catalog.items())
    ]

    client = _get_gemini_client()
    prompt = _build_faq_match_prompt(question_text, faq_catalog_for_prompt)
    response = client.models.generate_content(model=model, contents=prompt)

    response_text = (response.text or "").strip()
    if not response_text:
        return None

    parsed = _parse_faq_match_response(response_text)
    if not parsed:
        return None

    matched = _to_bool(parsed.get("matched"))
    if not matched:
        return None

    confidence = _to_float(parsed.get("confidence"), default=0.0)
    if confidence < similarity_threshold:
        return None

    faq_id_value = parsed.get("faq_id")
    if not isinstance(faq_id_value, int):
        return None

    item = catalog.get(faq_id_value)
    if not item:
        return None

    questions = item.get("questions")
    first_question = ""
    if isinstance(questions, list) and questions:
        first_question = str(questions[0])

    matched_question = str(parsed.get("matched_question") or first_question).strip()

    result: dict[str, int | str | float | Path] = {
        "faq_id": faq_id_value,
        "matched_question": matched_question,
        "faq_answer": str(item.get("answer", "")).strip(),
        "score": round(confidence, 4),
    }

    voice_path = item.get("voice_path")
    if isinstance(voice_path, Path):
        result["voice_path"] = voice_path

    return result


def gemini_answer_armenian(user_text: str, model: str = ANSWER_MODEL) -> str:
    """Generate a concise Armenian answer with Gemini."""
    extracted_input = _extract_user_input(user_text)
    if not is_mostly_armenian(extracted_input):
        return "Խնդրում եմ խոսել կամ գրել հայերենով։"

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Դու Սասի HR AI Agent ես։ "
                            "Միշտ պատասխանիր հայերենով։ "
                            "Եթե հարցնեն՝ ով ես, հստակ ասա, որ Սասի HR AI Agent ես։ "
                            "Պատասխանը պահիր շատ կարճ՝ 1-2 կարճ նախադասություն։ "
                            "Եթե տվյալը վստահ չգիտես, ասա կարճ, որ տվյալը չունես։\n\n"
                            f"Հարց/մուտք՝ {user_text}"
                        )
                    }
                ],
            }
        ],
    )

    answer = (response.text or "").strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty response.")

    if not is_mostly_armenian(answer):
        return "Խնդրում եմ խոսել կամ գրել հայերենով։"

    return answer


def main() -> None:
    """Manual CLI smoke test for local development."""
    prompt = "Ինչպե՞ս է եղանակը Երևանում գարնանը։"
    print(gemini_answer_armenian(prompt))


if __name__ == "__main__":
    main()
