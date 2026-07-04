"""HTML renderers for markdown article slide image series."""

from __future__ import annotations

import base64
import html
import shutil
import sys
from pathlib import Path
from typing import Any

from markdown_to_image.parser import (
    ContentBlock,
    load_manifest,
    merge_manifest_defaults,
    parse_article_file,
    resolve_source_path,
    validate_required_manifest_fields,
)
from markdown_to_image.browser_paginator import paginate_blocks_with_browser
from markdown_to_image.paginator import _merge_adjacent_blocks
from markdown_to_image.config import REPO_ROOT, enrich_manifest_from_article, load_renderer_config

_PACKAGE_DIR = Path(__file__).resolve().parent
_STYLES_DIR = _PACKAGE_DIR / "styles"
_CSS_PATH = _STYLES_DIR / "article.css"
_BODY_SLIDE_WARN_THRESHOLD = 12

COVER_AI_FILENAME = "cover-ai.png"
COVER_BASE_FILENAME = "cover-base.png"
COVER_BG_FILENAME = "cover-bg.png"
COVER_OUTPUT_FILENAME = "01-cover.png"

CTA_THEME_LABELS = {
    "reading": "读书感悟",
    "summary": "总结复盘",
    "life": "生活分享",
}
_ANNUAL_SUMMARY_KEYWORDS = ("年终", "年度", "年底", "年末")
_CATEGORY_ALIASES = {
    "summary": "zong-jie",
}

_CSS_BLOCK_CACHE: str | None = None


def _social_title(manifest: dict[str, Any]) -> str:
    return str(
        manifest.get("social_title")
        or manifest.get("series_title")
        or ""
    )


def _css_block() -> str:
    global _CSS_BLOCK_CACHE
    if _CSS_BLOCK_CACHE is None:
        base = (_STYLES_DIR / "base.css").read_text(encoding="utf-8")
        article = _CSS_PATH.read_text(encoding="utf-8")
        _CSS_BLOCK_CACHE = f"<style>{base}\n{article}</style>"
    return _CSS_BLOCK_CACHE


def clear_css_cache() -> None:
    """Drop cached inline CSS (tests / dev rerenders)."""
    global _CSS_BLOCK_CACHE
    _CSS_BLOCK_CACHE = None


def _slide_shell(
    body: str,
    extra_class: str = "",
    background_url: str | None = None,
    *,
    nickname: str = "",
    page: int = 0,
    total: int = 0,
    show_page_footer: bool = False,
) -> str:
    slide_class = f"slide {extra_class}".strip()
    style_attr = ""
    if background_url:
        style_attr = f' style="background-image: url(\'{background_url}\');"'
    footer_html = ""
    if show_page_footer:
        footer_html = f"""
    <div class="slide-footer">
      <span>@{html.escape(nickname)}</span>
      <span class="footer-page">{page}/{total}</span>
    </div>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  {_css_block()}
</head>
<body>
  <div class="{slide_class}"{style_attr}>
    <div class="slide-body">{body}</div>{footer_html}
  </div>
</body>
</html>"""


def _render_block_html(block_kind: str, text: str, *, paragraph_start: bool = True) -> str:
    escaped = html.escape(text)
    if block_kind == "quote":
        return f'<div class="article-quote">{escaped}</div>'
    paragraph_class = "article-p article-p-start" if paragraph_start else "article-p article-p-continue"
    return f'<p class="{paragraph_class}">{escaped}</p>'


def _collapse_paragraph_blocks(blocks: list) -> list:
    """Merge consecutive paragraph blocks from the same source for seamless rendering."""
    collapsed: list = []
    for block in blocks:
        if (
            collapsed
            and block.kind == "paragraph"
            and collapsed[-1].kind == "paragraph"
            and collapsed[-1].source_id == block.source_id
        ):
            previous = collapsed[-1]
            collapsed[-1] = ContentBlock(
                previous.kind,
                previous.text + block.text,
                previous.source_id,
            )
            continue
        collapsed.append(block)
    return collapsed


def _render_body_page(
    header: str,
    blocks: list,
    page: int,
    total: int,
    nickname: str,
    *,
    continues_paragraph: bool = False,
) -> str:
    parts: list[str] = []
    seen_sources: set[int] = set()
    for index, block in enumerate(_collapse_paragraph_blocks(blocks)):
        if block.kind == "quote":
            parts.append(_render_block_html(block.kind, block.text))
            continue

        paragraph_start = True
        if block.source_id in seen_sources:
            paragraph_start = False
        elif index == 0 and continues_paragraph:
            paragraph_start = False
        seen_sources.add(block.source_id)
        parts.append(_render_block_html(block.kind, block.text, paragraph_start=paragraph_start))

    body = f"""
    <div class="frame-header">{html.escape(header)}</div>
    <div class="article-body-text">{"".join(parts)}</div>
    """
    return _slide_shell(
        body,
        extra_class="slide-article",
        nickname=nickname,
        page=page,
        total=total,
        show_page_footer=True,
    )


def _resolve_article_image_path(src: str, source_path: Path, project_root: Path | None = None) -> Path:
    clean_src = src.strip()
    if not clean_src:
        raise ValueError("Article image block missing src")

    path = Path(clean_src)
    if path.is_absolute() and path.is_file():
        return path

    candidates: list[Path] = []
    if clean_src.startswith("/"):
        site_path = clean_src.lstrip("/")
        if project_root is not None:
            candidates.append(project_root / "static" / site_path)
            candidates.append(project_root / site_path)
        candidates.append(REPO_ROOT / "static" / site_path)
    else:
        candidates.append(source_path.parent / clean_src)
        if project_root is not None:
            candidates.append(project_root / clean_src)
            candidates.append(project_root / "static" / clean_src)
        candidates.append(REPO_ROOT / clean_src)
        candidates.append(REPO_ROOT / "static" / clean_src)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    resolved = candidates[0] if candidates else path
    raise FileNotFoundError(f"Article image missing: {clean_src} (resolved to {resolved})")


def _render_image_page(
    block: ContentBlock,
    source_path: Path,
    project_root: Path | None,
    page: int,
    total: int,
    nickname: str,
) -> str:
    image_path = _resolve_article_image_path(block.image_src, source_path, project_root)
    caption = block.text.strip()
    alt = block.image_alt.strip() or caption or "文章配图"
    caption_html = (
        f'<div class="article-photo-caption">{html.escape(caption)}</div>' if caption else ""
    )
    body = f"""
    <div class="article-photo-card">
      <div class="article-photo-media">
        <img class="article-photo-img" src="{_image_data_url(image_path)}" alt="{html.escape(alt)}" />
      </div>
      {caption_html}
    </div>
    """
    return _slide_shell(
        body,
        extra_class="slide-article slide-photo",
        nickname=nickname,
        page=page,
        total=total,
        show_page_footer=True,
    )


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _project_root_from_manifest(manifest: dict[str, Any]) -> Path | None:
    raw = manifest.get("project_root")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw.strip()).expanduser().resolve()


def _iter_block_segments(blocks: list[ContentBlock]) -> list[tuple[str, list[ContentBlock] | ContentBlock]]:
    segments: list[tuple[str, list[ContentBlock] | ContentBlock]] = []
    text_blocks: list[ContentBlock] = []
    for block in blocks:
        if block.kind == "image":
            if text_blocks:
                segments.append(("text", text_blocks))
                text_blocks = []
            segments.append(("image", block))
            continue
        text_blocks.append(block)
    if text_blocks:
        segments.append(("text", text_blocks))
    return segments


def _matches_rendered_cover(candidate: Path, manifest_dir: Path) -> bool:
    rendered_cover = manifest_dir / COVER_OUTPUT_FILENAME
    if not rendered_cover.is_file():
        return False
    return candidate.read_bytes() == rendered_cover.read_bytes()


def prepare_cover_base(manifest_dir: Path, manifest: dict[str, Any]) -> Path | None:
    """Return the optional cover base image used behind the rendered title."""
    base_path = manifest_dir / COVER_BASE_FILENAME
    declared_background = False
    skipped_rendered_cover_copy = False
    for key in ("cover_base", "cover_ai", "cover_bg"):
        name = manifest.get(key)
        if not isinstance(name, str) or not name.strip():
            continue
        declared_background = True
        candidate = manifest_dir / name.strip()
        if not candidate.is_file():
            continue
        if _matches_rendered_cover(candidate, manifest_dir):
            skipped_rendered_cover_copy = True
            continue
        if candidate.resolve() != base_path.resolve():
            shutil.copy2(candidate, base_path)
            return base_path
        if candidate.is_file():
            return candidate

    if declared_background and not skipped_rendered_cover_copy:
        raise FileNotFoundError(
            f"Declared cover base missing. Expected {base_path} or the manifest cover path in {manifest_dir}"
        )

    return None


def _resolve_cta_theme_label(manifest: dict[str, Any]) -> str:
    explicit_label = str(manifest.get("cta_label") or "").strip()
    if explicit_label:
        return explicit_label

    primary_category = str(manifest.get("primary_category") or "").strip()
    primary_category = _CATEGORY_ALIASES.get(primary_category, primary_category)
    if primary_category == "zong-jie":
        title_text = "".join(
            str(manifest.get(key) or "")
            for key in ("original_title", "social_title", "series_title")
        )
        if any(keyword in title_text for keyword in _ANNUAL_SUMMARY_KEYWORDS):
            return "年度总结"
        return CTA_THEME_LABELS["summary"]

    theme = str(manifest.get("cta_theme") or "reading").strip() or "reading"
    return CTA_THEME_LABELS.get(theme, theme)


def _cover_title_scale_class(title: str) -> str:
    compact_length = len("".join(title.split()))
    if compact_length <= 12:
        return "cover-title-short"
    if compact_length <= 24:
        return "cover-title-medium"
    return "cover-title-long"


def _render_cover_slide(manifest: dict[str, Any], manifest_dir: Path) -> str:
    base_path = prepare_cover_base(manifest_dir, manifest)
    social_title = _social_title(manifest)
    theme_label = _resolve_cta_theme_label(manifest)
    title_scale_class = _cover_title_scale_class(social_title)

    body = f"""
    <div class="cover-title-card glass-card">
      <div class="cover-kicker">{html.escape(theme_label)}</div>
      <div class="cover-title {title_scale_class}">{html.escape(social_title)}</div>
    </div>
    """
    return _slide_shell(
        body,
        extra_class="slide-cover",
        background_url=_image_data_url(base_path) if base_path else None,
    )


def _render_end_slide(manifest: dict[str, Any]) -> str:
    theme_label = _resolve_cta_theme_label(manifest)
    line1 = str(manifest.get("cta_line1") or "")
    nickname = str(manifest.get("nickname") or "")
    bio = str(manifest.get("bio") or "")

    body = f"""
    <div class="end-theme">{html.escape(theme_label)}</div>
    <div class="end-line">{html.escape(line1)}</div>
    <div class="end-handle">@{html.escape(nickname)}</div>
    <div class="end-bio">{html.escape(bio)}</div>
    """
    return _slide_shell(body, extra_class="slide-end")


def render_article_slides(manifest_path: Path) -> tuple[list[tuple[str, str]], Path]:
    manifest_path = manifest_path.resolve()
    manifest_dir = manifest_path.parent
    raw_manifest = load_manifest(manifest_path)
    project_root = _project_root_from_manifest(raw_manifest)
    config = load_renderer_config(manifest_dir, project_root)
    manifest = merge_manifest_defaults(raw_manifest, config)
    project_root = _project_root_from_manifest(manifest)
    validate_required_manifest_fields(manifest)

    source_path = resolve_source_path(manifest, manifest_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Article source missing: {source_path}")

    article = parse_article_file(source_path)
    manifest = enrich_manifest_from_article(manifest, article.metadata, config, project_root)
    if not article.blocks:
        raise ValueError(f"No content blocks after parsing: {source_path}")

    max_chars = int(manifest.get("chars_per_slide", 340))

    header = _social_title(manifest)
    nickname = str(manifest.get("nickname") or "")

    def _page_continues_from_previous(all_pages: list, page_index: int, blocks: list) -> bool:
        if page_index <= 0 or not all_pages[page_index - 1] or not blocks:
            return False
        previous_last = all_pages[page_index - 1][-1]
        first_block = blocks[0]
        return (
            previous_last.kind == "paragraph"
            and first_block.kind == "paragraph"
            and previous_last.source_id == first_block.source_id
        )

    def _render_probe_page(blocks: list, probe_total: int, page_index: int = 0, all_pages: list | None = None) -> str:
        pages_snapshot = all_pages if all_pages is not None else [blocks]
        continues = _page_continues_from_previous(pages_snapshot, page_index, blocks)
        return _render_body_page(
            header,
            blocks,
            1,
            max(probe_total, 1),
            nickname,
            continues_paragraph=continues,
        )

    body_slides: list[tuple[str, list[ContentBlock] | ContentBlock]] = []
    for segment_kind, segment in _iter_block_segments(article.blocks):
        if segment_kind == "image":
            body_slides.append((segment_kind, segment))
            continue

        text_segment = segment
        assert isinstance(text_segment, list)
        body_pages = paginate_blocks_with_browser(
            text_segment,
            _render_probe_page,
            max_chars=max_chars,
        )
        body_pages = [_merge_adjacent_blocks(page) for page in body_pages if page]
        for page in body_pages:
            body_slides.append(("text", page))

    if len(body_slides) > _BODY_SLIDE_WARN_THRESHOLD:
        print(
            f"Warning: {len(body_slides)} body slides (>{_BODY_SLIDE_WARN_THRESHOLD}); "
            f"consider raising chars_per_slide in manifest (current {max_chars}).",
            file=sys.stderr,
            flush=True,
        )

    body_total = len(body_slides)

    slides: list[tuple[str, str]] = []
    slides.append((COVER_OUTPUT_FILENAME, _render_cover_slide(manifest, manifest_dir)))

    previous_text_page: list[ContentBlock] | None = None
    for index, (slide_kind, slide_content) in enumerate(body_slides, start=1):
        filename = f"{index + 1:02d}.png"
        if slide_kind == "image":
            assert isinstance(slide_content, ContentBlock)
            html_doc = _render_image_page(
                slide_content,
                source_path,
                project_root,
                index,
                body_total,
                nickname,
            )
            slides.append((filename, html_doc))
            previous_text_page = None
            continue

        blocks = slide_content
        assert isinstance(blocks, list)
        continues_paragraph = False
        if previous_text_page and blocks:
            previous_last = previous_text_page[-1]
            first_block = blocks[0]
            continues_paragraph = (
                previous_last.kind == "paragraph"
                and first_block.kind == "paragraph"
                and previous_last.source_id == first_block.source_id
            )
        html_doc = _render_body_page(
            header,
            blocks,
            index,
            body_total,
            nickname,
            continues_paragraph=continues_paragraph,
        )
        slides.append((filename, html_doc))
        previous_text_page = blocks

    end_page_num = body_total + 2
    slides.append((f"{end_page_num:02d}-end.png", _render_end_slide(manifest)))
    return slides, manifest_dir
