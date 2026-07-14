"""Parse article markdown for slide image generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

import yaml

from markdown_to_image.config import SUPPORTED_MANIFEST_VERSION, normalize_platform

_INLINE_LINK_RE = re.compile(
    r' <small>（<a href="([^"]+)" rel="noopener noreferrer">原文链接</a>'
    r"(?:，更新于\d{4}-\d{2}-\d{2}。)?）</small>"
)
_INLINE_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((?:[^()\\]|\\.|[^()])*?\)")
_IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_IMAGE_MARKDOWN_BLOCK_RE = re.compile(
    r'^!\[([^\]]*)\]\((\S+?)(?:\s+["\'][^"\']*["\'])?\)$'
)
_FIGURE_HTML_RE = re.compile(r"<figure\b", re.IGNORECASE)
_FENCE_CHARS = ("`", "~")
_CTA_BLOCK_RE = re.compile(
    r'\n*<div class="article-follow-cta">.*?</div>\s*',
    re.DOTALL,
)
_PROMO_LINE_RE = re.compile(r"^\s*【?\s*↓↓↓")
BASE_REQUIRED_MANIFEST_FIELDS = (
    "source",
    "original_title",
    "social_title",
)
REDNOTE_REQUIRED_MANIFEST_FIELDS = (
    "cta_line1",
)


class MarkdownPost:
    __slots__ = ("metadata", "content")

    def __init__(self, metadata: dict[str, Any], content: str) -> None:
        self.metadata = metadata
        self.content = content


def parse_frontmatter_markdown(text: str) -> MarkdownPost:
    if text.startswith("\ufeff"):
        text = text[1:]
    stripped = text.lstrip("\n\r")
    if not stripped.startswith("---"):
        return MarkdownPost({}, text)

    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return MarkdownPost({}, text)

    end_idx: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_idx = index
            break
    if end_idx is None:
        return MarkdownPost({}, text)

    fm_block = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    if body.startswith("\n"):
        body = body[1:]

    meta_raw = yaml.safe_load(fm_block)
    meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    return MarkdownPost(meta, body)


def strip_cta_html(body: str) -> str:
    out = _CTA_BLOCK_RE.sub("\n", body)
    return out.rstrip("\n") + "\n"


def strip_trailing_promo_lines(body: str) -> str:
    lines = body.split("\n")
    while lines:
        last = lines[-1]
        if not last.strip():
            lines.pop()
            continue
        if _PROMO_LINE_RE.match(last):
            lines.pop()
            continue
        break
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


@dataclass(frozen=True)
class ContentBlock:
    kind: Literal["paragraph", "quote", "image", "code"]
    text: str
    source_id: int = 0
    image_src: str = ""
    image_alt: str = ""
    code_language: str = ""

    def with_text(self, text: str, source_id: int | None = None) -> "ContentBlock":
        return ContentBlock(
            self.kind,
            text,
            self.source_id if source_id is None else source_id,
            self.image_src,
            self.image_alt,
            self.code_language,
        )


@dataclass
class ParsedArticle:
    metadata: dict[str, Any]
    body: str
    blocks: list[ContentBlock]
    has_embedded_images: bool


def strip_inline_markdown_links(text: str) -> str:
    """Replace [anchor](url) with anchor text only."""
    lines = text.splitlines()
    out: list[str] = []
    index = 0
    in_fence = False
    fence_char = ""
    fence_len = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if in_fence:
            out.append(line)
            if _is_code_fence_end(stripped, fence_char, fence_len):
                in_fence = False
            index += 1
            continue

        fence_start = _parse_code_fence_start(stripped)
        if fence_start is not None:
            fence_char, fence_len, _language = fence_start
            in_fence = True
            out.append(line)
            index += 1
            continue

        if _is_indented_code_line(line):
            while index < len(lines):
                current = lines[index]
                if _is_indented_code_line(current):
                    out.append(current)
                    index += 1
                    continue
                if not current.strip() and _next_nonblank_line_is_indented_code(lines, index):
                    out.append(current)
                    index += 1
                    continue
                break
            continue

        out.append(_INLINE_MARKDOWN_LINK_RE.sub(r"\1", line))
        index += 1

    return "\n".join(out)


def strip_body_for_slides(body: str) -> str:
    text = strip_cta_html(body)
    text = _INLINE_LINK_RE.sub("", text)
    text = strip_trailing_promo_lines(text)
    text = strip_inline_markdown_links(text)
    return text.strip()


def detect_embedded_images(body: str) -> bool:
    return bool(_IMAGE_MARKDOWN_RE.search(body) or _FIGURE_HTML_RE.search(body))


class _FigureImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image_src = ""
        self.image_alt = ""
        self._in_caption = False
        self._caption_parts: list[str] = []

    @property
    def caption(self) -> str:
        return "".join(self._caption_parts).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "img" and not self.image_src:
            attr_map = {key.lower(): value or "" for key, value in attrs}
            self.image_src = attr_map.get("src", "").strip()
            self.image_alt = attr_map.get("alt", "").strip()
        elif normalized == "figcaption":
            self._in_caption = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "figcaption":
            self._in_caption = False

    def handle_data(self, data: str) -> None:
        if self._in_caption:
            self._caption_parts.append(data)


def _parse_figure_block(markup: str) -> ContentBlock | None:
    parser = _FigureImageParser()
    parser.feed(markup)
    if not parser.image_src:
        return None
    caption = parser.caption or parser.image_alt
    return ContentBlock(
        "image",
        caption,
        image_src=parser.image_src,
        image_alt=parser.image_alt,
    )


def _parse_markdown_image_line(line: str) -> ContentBlock | None:
    match = _IMAGE_MARKDOWN_BLOCK_RE.match(line.strip())
    if not match:
        return None
    alt, src = match.groups()
    alt = alt.strip()
    return ContentBlock("image", alt, image_src=src.strip(), image_alt=alt)


def _parse_code_fence_start(stripped: str) -> tuple[str, int, str] | None:
    if not stripped or stripped[0] not in _FENCE_CHARS:
        return None
    fence_char = stripped[0]
    fence_len = 0
    while fence_len < len(stripped) and stripped[fence_len] == fence_char:
        fence_len += 1
    if fence_len < 3:
        return None
    info = stripped[fence_len:].strip()
    language = info.split(None, 1)[0].strip() if info else ""
    return fence_char, fence_len, language


def _is_code_fence_end(stripped: str, fence_char: str, fence_len: int) -> bool:
    if not stripped.startswith(fence_char * fence_len):
        return False
    return set(stripped).issubset({fence_char})


def _is_indented_code_line(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _strip_code_indent(line: str) -> str:
    if line.startswith("\t"):
        return line[1:]
    if line.startswith("    "):
        return line[4:]
    return line


def _clean_code_text(lines: list[str]) -> str:
    text = "\n".join(line.rstrip().replace("\u00a0", " ") for line in lines)
    return text.strip("\n")


def _next_nonblank_line_is_indented_code(lines: list[str], index: int) -> bool:
    probe = index + 1
    while probe < len(lines):
        if lines[probe].strip():
            return _is_indented_code_line(lines[probe])
        probe += 1
    return False


def _starts_special_block(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith(">")
        or stripped.lower().startswith("<figure")
        or _parse_markdown_image_line(stripped) is not None
        or _parse_code_fence_start(stripped) is not None
        or _is_indented_code_line(line)
    )


def parse_body_blocks(body: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines):
                current = lines[index]
                if current.strip().startswith(">"):
                    quote_lines.append(re.sub(r"^>\s?", "", current.strip()))
                    index += 1
                elif not current.strip() and quote_lines:
                    index += 1
                    break
                else:
                    break
            blocks.append(ContentBlock("quote", "\n".join(quote_lines).strip()))
            continue
        fence_start = _parse_code_fence_start(stripped)
        if fence_start is not None:
            fence_char, fence_len, language = fence_start
            code_lines: list[str] = []
            index += 1
            while index < len(lines):
                current = lines[index]
                if _is_code_fence_end(current.strip(), fence_char, fence_len):
                    index += 1
                    break
                code_lines.append(current)
                index += 1
            blocks.append(ContentBlock("code", _clean_code_text(code_lines), code_language=language))
            continue
        if _is_indented_code_line(line):
            code_lines = []
            while index < len(lines):
                current = lines[index]
                if _is_indented_code_line(current):
                    code_lines.append(_strip_code_indent(current))
                    index += 1
                    continue
                if not current.strip() and _next_nonblank_line_is_indented_code(lines, index):
                    code_lines.append("")
                    index += 1
                    continue
                break
            blocks.append(ContentBlock("code", _clean_code_text(code_lines)))
            continue
        markdown_image = _parse_markdown_image_line(stripped)
        if markdown_image is not None:
            blocks.append(markdown_image)
            index += 1
            continue
        if stripped.lower().startswith("<figure"):
            figure_lines: list[str] = []
            while index < len(lines):
                current = lines[index]
                figure_lines.append(current)
                index += 1
                if "</figure>" in current.lower():
                    break
            figure_block = _parse_figure_block("\n".join(figure_lines))
            if figure_block is not None:
                blocks.append(figure_block)
            continue

        paragraph_lines: list[str] = []
        while index < len(lines):
            current = lines[index]
            current_stripped = current.strip()
            if not current_stripped:
                break
            if _starts_special_block(current):
                break
            paragraph_lines.append(current)
            index += 1
        blocks.append(ContentBlock("paragraph", "\n".join(paragraph_lines).strip()))
    return [block for block in blocks if block.text or block.kind == "image"]


def parse_article_file(path: Path) -> ParsedArticle:
    raw = path.read_text(encoding="utf-8")
    post = parse_frontmatter_markdown(raw)
    body = strip_body_for_slides(post.content)
    return ParsedArticle(
        metadata=post.metadata,
        body=body,
        blocks=parse_body_blocks(body),
        has_embedded_images=detect_embedded_images(post.content),
    )


def load_manifest(path: Path) -> dict[str, Any]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    version = data.get("manifest_version", 1)
    if version != SUPPORTED_MANIFEST_VERSION:
        raise ValueError(
            f"Unsupported manifest_version {version!r} in {path}; "
            f"expected {SUPPORTED_MANIFEST_VERSION}"
        )
    return data


def validate_required_manifest_fields(manifest: dict[str, Any]) -> None:
    required_fields = list(BASE_REQUIRED_MANIFEST_FIELDS)
    if normalize_platform(manifest.get("platform")) == "rednote":
        required_fields.extend(REDNOTE_REQUIRED_MANIFEST_FIELDS)
    missing = [
        field
        for field in required_fields
        if not str(manifest.get(field) or "").strip()
    ]
    if missing:
        raise ValueError(f"manifest missing required fields: {', '.join(missing)}")


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _set_default_if_blank(
    merged: dict[str, Any],
    key: str,
    config: dict[str, Any],
    fallback: Any = None,
) -> None:
    if not _is_blank(merged.get(key)):
        return
    value = config.get(key, fallback)
    if _is_blank(value):
        value = fallback
    if not _is_blank(value):
        merged[key] = value


def merge_manifest_defaults(manifest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    merged = dict(manifest)
    _set_default_if_blank(merged, "platform", config, "rednote")
    _set_default_if_blank(merged, "project_root", config)
    _set_default_if_blank(merged, "nickname", config)
    _set_default_if_blank(merged, "bio", config)
    _set_default_if_blank(merged, "chars_per_slide", config, 340)
    _set_default_if_blank(merged, "x_include_images", config)
    return merged


def resolve_source_path(manifest: dict[str, Any], manifest_path: Path) -> Path:
    source = manifest.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("manifest missing source path")
    source_path = Path(source.strip())
    if source_path.is_absolute():
        return source_path

    candidates = [manifest_path.parent / source_path, Path.cwd() / source_path]
    project_root = manifest.get("project_root")
    if isinstance(project_root, str) and project_root.strip():
        candidates.insert(0, Path(project_root.strip()).expanduser() / source_path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[-1].resolve()
