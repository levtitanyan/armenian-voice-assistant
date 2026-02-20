from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9\u0531-\u058F]+")


@dataclass
class KnowledgeItem:
    item_id: str
    source_type: str
    source: str
    text: str
    meta: dict[str, Any]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    cleaned = _normalize_whitespace(text)
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[\.\!\?։])\s+", cleaned):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if re.match(r"^\d+\.", stripped):
        return True
    return "?" in stripped or "՞" in stripped


def _load_faq_from_single_column(faq_path: Path) -> list[KnowledgeItem]:
    import pandas as pd

    df = pd.read_excel(faq_path, header=None)
    if df.empty:
        return []

    first_col = df.iloc[:, 0].tolist()
    lines = [_normalize_whitespace(str(value)) for value in first_col if str(value).strip().lower() != "nan"]
    if not lines:
        return []

    # Drop a title-like first line if present.
    if "հաճախակի" in lines[0].lower() and not _looks_like_question(lines[0]):
        lines = lines[1:]

    items: list[KnowledgeItem] = []
    current_question = ""
    answer_parts: list[str] = []

    def flush_item() -> None:
        nonlocal current_question, answer_parts
        question = _normalize_whitespace(current_question)
        answer = _normalize_whitespace(" ".join(answer_parts))
        if question and answer:
            text = f"Հարց: {question}\nՊատասխան: {answer}"
            items.append(
                KnowledgeItem(
                    item_id=f"faq-{len(items) + 1}",
                    source_type="faq",
                    source=faq_path.name,
                    text=text,
                    meta={},
                )
            )
        current_question = ""
        answer_parts = []

    for line in lines:
        if _looks_like_question(line):
            if current_question:
                flush_item()
            current_question = line
        else:
            if current_question:
                answer_parts.append(line)

    if current_question:
        flush_item()

    return items


def load_faq_from_excel(faq_path: Path) -> list[KnowledgeItem]:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to load FAQ Excel files. Install with: pip install pandas openpyxl"
        ) from exc

    if not faq_path.exists():
        raise FileNotFoundError(f"FAQ file not found: {faq_path}")

    df = pd.read_excel(faq_path)
    df.columns = [str(column).strip().lower() for column in df.columns]

    question_col = None
    answer_col = None
    for candidate in ("question", "հարց", "faq_question"):
        if candidate in df.columns:
            question_col = candidate
            break
    for candidate in ("answer", "պատասխան", "faq_answer"):
        if candidate in df.columns:
            answer_col = candidate
            break

    if not question_col or not answer_col:
        fallback_items = _load_faq_from_single_column(faq_path)
        if fallback_items:
            return fallback_items
        raise RuntimeError(
            "FAQ Excel must include question/answer columns or use a single-column Q/A layout. "
            f"Found columns: {', '.join(df.columns)}"
        )

    items: list[KnowledgeItem] = []
    for idx, row in df.iterrows():
        question = _normalize_whitespace(str(row.get(question_col, "")))
        answer = _normalize_whitespace(str(row.get(answer_col, "")))
        if not question or not answer:
            continue
        category = _normalize_whitespace(str(row.get("category", "")))
        text = f"Հարց: {question}\nՊատասխան: {answer}"
        items.append(
            KnowledgeItem(
                item_id=f"faq-{idx + 1}",
                source_type="faq",
                source=faq_path.name,
                text=text,
                meta={"category": category} if category else {},
            )
        )
    return items


def load_transcripts_from_dir(transcript_dir: Path) -> list[KnowledgeItem]:
    if not transcript_dir.exists():
        return []

    items: list[KnowledgeItem] = []
    text_files = sorted(transcript_dir.rglob("*.txt"))
    for file_index, path in enumerate(text_files, start=1):
        content = _normalize_whitespace(path.read_text(encoding="utf-8", errors="ignore"))
        if not content:
            continue
        for chunk_index, chunk in enumerate(_chunk_text(content), start=1):
            items.append(
                KnowledgeItem(
                    item_id=f"call-{file_index}-{chunk_index}",
                    source_type="call_transcript",
                    source=path.name,
                    text=chunk,
                    meta={"path": str(path)},
                )
            )
    return items


def save_knowledge_items(items: list[KnowledgeItem], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(item) for item in items]
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_knowledge_items(knowledge_path: Path) -> list[KnowledgeItem]:
    if not knowledge_path.exists():
        return []
    raw = json.loads(knowledge_path.read_text(encoding="utf-8"))
    items: list[KnowledgeItem] = []
    for row in raw:
        items.append(
            KnowledgeItem(
                item_id=str(row.get("item_id", "")),
                source_type=str(row.get("source_type", "")),
                source=str(row.get("source", "")),
                text=str(row.get("text", "")),
                meta=dict(row.get("meta", {})),
            )
        )
    return items


def retrieve_relevant_items(
    query: str,
    items: list[KnowledgeItem],
    top_k: int = 5,
) -> list[KnowledgeItem]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return items[:top_k]

    scored: list[tuple[float, KnowledgeItem]] = []
    for item in items:
        text_tokens = _tokenize(item.text)
        if not text_tokens:
            continue

        overlap = len(query_tokens.intersection(text_tokens))
        if overlap == 0:
            continue
        score = overlap / max(1, len(query_tokens))
        faq_bonus = 0.15 if item.source_type == "faq" else 0.0
        scored.append((score + faq_bonus, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def format_context(items: list[KnowledgeItem]) -> str:
    if not items:
        return "No SAS HR knowledge context found."
    lines: list[str] = []
    for idx, item in enumerate(items, start=1):
        lines.append(f"[{idx}] source={item.source_type}:{item.source}")
        lines.append(item.text)
    return "\n\n".join(lines)
