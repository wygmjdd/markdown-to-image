"""Human-readable output directory names for rendered article slides."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pypinyin import lazy_pinyin

DEFAULT_ARTICLES_OUTPUT_ROOT = Path.cwd() / "markdown-to-image-output" / "articles"


def title_to_pinyin_dir(title: str) -> str:
    """Map article title to hyphenated pinyin (e.g. 特斯拉与外星人 → te-si-la-yu-wai-xing-ren)."""
    stripped = title.strip()
    if not stripped:
        return "untitled"

    segments: list[str] = []
    for part in lazy_pinyin(stripped):
        cleaned = re.sub(r"[^a-z0-9]", "", part.lower())
        if cleaned:
            segments.append(cleaned)

    if not segments:
        return "untitled"
    return "-".join(segments)


def source_slug_from_path(source_path: Path) -> str:
    return source_path.stem


def post_id_suffix(source_path: Path) -> str:
    stem = source_path.stem
    marker = "__post-"
    if marker in stem:
        return stem.rsplit(marker, 1)[-1]
    return stem


def _same_source_in_manifest(manifest_path: Path, source_path: Path, repo_root: Path) -> bool:
    if not manifest_path.is_file():
        return False
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False

    recorded = data.get("source")
    if not isinstance(recorded, str) or not recorded.strip():
        return False

    recorded_path = Path(recorded.strip())
    if not recorded_path.is_absolute():
        recorded_path = repo_root / recorded_path
    return recorded_path.resolve() == source_path.resolve()


def resolve_article_output_dir(
    title: str,
    source_path: Path,
    articles_root: Path | None = None,
    repo_root: Path | None = None,
) -> str:
    """Pick output folder name under output/articles/; disambiguate on title collision."""
    root = (articles_root or DEFAULT_ARTICLES_OUTPUT_ROOT).resolve()
    resolved_source = source_path.resolve()
    repo = (repo_root or Path.cwd()).resolve()

    base = title_to_pinyin_dir(title)
    candidate_dir = root / base
    if not candidate_dir.is_dir():
        return base

    manifest_path = candidate_dir / "manifest.json"
    if _same_source_in_manifest(manifest_path, resolved_source, repo):
        return base

    return f"{base}-{post_id_suffix(resolved_source)}"


def article_output_path(
    title: str,
    source_path: Path,
    articles_root: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    dir_name = resolve_article_output_dir(title, source_path, articles_root, repo_root)
    root = articles_root or DEFAULT_ARTICLES_OUTPUT_ROOT
    return root / dir_name
