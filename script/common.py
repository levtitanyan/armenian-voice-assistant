"""Shared helpers for assistant scripts (paths and Armenian text utilities)."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARMENIAN_CHAR_PATTERN = re.compile(r"[Ա-Ֆա-ֆև]")


def display_path(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    """Return a short project-relative path when possible."""
    try:
        relative = path.resolve().relative_to(project_root)
        return f"{project_root.name}/{relative.as_posix()}"
    except ValueError:
        return str(path)


def resolve_project_path(path_value: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """Resolve a path string or `Path` relative to project root."""
    path = Path(path_value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def normalize_for_similarity(text: str) -> str:
    """Normalize text for intent/FAQ similarity comparisons."""
    lowered = text.lower()
    lowered = re.sub(r"[^\wԱ-Ֆա-ֆЁё\s]", " ", lowered)
    return " ".join(lowered.split())


def armenian_letter_ratio(text: str) -> float:
    """Return ratio of Armenian letters among alphabetic letters."""
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    armenian_count = sum(1 for char in letters if ARMENIAN_CHAR_PATTERN.match(char))
    return armenian_count / len(letters)


def is_mostly_armenian(
    text: str,
    min_ratio: float = 0.35,
    min_armenian_letters: int = 2,
) -> bool:
    """Check whether text is mostly Armenian based on ratio and minimum letter count."""
    armenian_letters = ARMENIAN_CHAR_PATTERN.findall(text)
    if len(armenian_letters) < min_armenian_letters:
        return False
    return armenian_letter_ratio(text) >= min_ratio
