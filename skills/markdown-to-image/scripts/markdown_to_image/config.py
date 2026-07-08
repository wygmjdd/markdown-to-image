"""Load markdown-to-image config and optional project category titles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path.cwd()
CONFIG_FILENAMES = (
    "markdown-to-image.config.yml",
    ".markdown-to-image.yml",
)
CATEGORIES_PATH = REPO_ROOT / "data" / "categories.yml"
SUPPORTED_MANIFEST_VERSION = 1

DEFAULT_CONFIG: dict[str, Any] = {
    "platform": "rednote",
    "nickname": "作者",
    "bio": "",
    "chars_per_slide": 340,
    "default_cta": "reading",
    "cta_mapping": {
        "reading": [
            "reading",
            "yue-du-shu-mu",
            "du-shu",
            "shu-zhong-jin-ju-fen-xiang",
            "jin-ba-duo-pu-tong-xin-li-xue",
        ],
        "summary": ["summary", "zong-jie"],
        "life": [
            "life",
            "sheng-huo-ri-ji",
            "di-tie-ri-ji",
            "30-fen-zhong-ri-ji",
            "xue-zuo-cai",
            "jie-hun-zhe-jian-shi",
            "qin-mi-guan-xi",
            "shen-zhen",
            "zhi-chang-jing-li",
            "ji-shu-bo-ke",
        ],
    },
}

_PLATFORM_ALIASES = {
    "rednote": "rednote",
    "xiaohongshu": "rednote",
    "小红书": "rednote",
    "x": "x",
    "twitter": "x",
}


def normalize_platform(value: Any) -> str:
    raw = str(value or DEFAULT_CONFIG["platform"]).strip().lower()
    platform = _PLATFORM_ALIASES.get(raw)
    if platform is None:
        supported = ", ".join(sorted({"rednote", "x"}))
        raise ValueError(f"Unsupported platform {value!r}; expected one of: {supported}")
    return platform


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _unique_roots(*roots: Path | None) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in (*roots, Path.cwd()):
        if root is None:
            continue
        resolved = root.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _find_config_path(*roots: Path | None) -> Path | None:
    searched: set[Path] = set()
    for search_root in _unique_roots(*roots):
        for candidate_root in (search_root, *search_root.parents):
            if candidate_root in searched:
                continue
            searched.add(candidate_root)
            for filename in CONFIG_FILENAMES:
                candidate = candidate_root / filename
                if candidate.is_file():
                    return candidate
    return None


def load_renderer_config(*roots: Path | None) -> dict[str, Any]:
    config_path = _find_config_path(*roots)
    if config_path is None:
        return dict(DEFAULT_CONFIG)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config format: {config_path}")
    return _deep_merge(DEFAULT_CONFIG, data)


def load_category_titles(root: Path | None = None) -> dict[str, str]:
    categories_path = (root.expanduser().resolve() if root is not None else REPO_ROOT) / "data" / "categories.yml"
    if not categories_path.is_file():
        return {}
    raw = yaml.safe_load(categories_path.read_text(encoding="utf-8"))
    titles: dict[str, str] = {}
    if isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict) and row.get("slug"):
                titles[str(row["slug"]).strip()] = str(row.get("title") or row["slug"]).strip()
    return titles


def resolve_category_title(slug: str, root: Path | None = None) -> str:
    return load_category_titles(root).get(slug, slug)


def resolve_cta_theme(primary_category: str, config: dict[str, Any] | None = None) -> str:
    cfg = config or load_renderer_config()
    mapping = cfg.get("cta_mapping") or {}
    for theme, slugs in mapping.items():
        if isinstance(slugs, list) and primary_category in slugs:
            return str(theme)
    default = cfg.get("default_cta", "reading")
    return str(default)


def enrich_manifest_from_article(
    manifest: dict[str, Any],
    article_metadata: dict[str, Any],
    config: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Fill category fields from article frontmatter when manifest omits them."""
    merged = dict(manifest)
    if not str(merged.get("primary_category") or "").strip():
        slug_raw = article_metadata.get("primary_category")
        if slug_raw is not None and str(slug_raw).strip():
            merged["primary_category"] = str(slug_raw).strip()

    slug = str(merged.get("primary_category") or "").strip()
    if slug and not str(merged.get("category_title") or "").strip():
        merged["category_title"] = resolve_category_title(slug, project_root)
    if not str(merged.get("cta_theme") or "").strip() and not str(merged.get("cta_label") or "").strip():
        merged["cta_theme"] = resolve_cta_theme(slug, config)
    return merged
