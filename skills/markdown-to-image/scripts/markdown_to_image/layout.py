"""Layout constants and height estimation for article slide pagination."""

from __future__ import annotations

from markdown_to_image.parser import ContentBlock

SLIDE_HEIGHT = 1440
SLIDE_PADDING_TOP = 32
SLIDE_PADDING_BOTTOM = 56
BODY_PADDING_VERTICAL = 32 + 28
FRAME_HEADER_LINES = 1
FRAME_HEADER_FONT = 24
FRAME_HEADER_LINE_HEIGHT = 1.5
FRAME_HEADER_MARGIN = 22
FRAME_HEADER_PADDING = 16
CONTENT_WIDTH = 1080 - 36 * 2 - 36 * 2

PARAGRAPH_FONT = 33
PARAGRAPH_LINE_HEIGHT = 1.86
QUOTE_FONT = 29
QUOTE_LINE_HEIGHT = 1.78
QUOTE_PADDING_VERTICAL = 24
QUOTE_PADDING_HORIZONTAL = 42
CODE_FONT = 22
CODE_LINE_HEIGHT = 1.58
CODE_PADDING_VERTICAL = 44
CODE_PADDING_HORIZONTAL = 58
BLOCK_GAP = 28
DEFAULT_SPLIT_CHARS = 340


def _header_height(lines: int) -> float:
    return lines * FRAME_HEADER_FONT * FRAME_HEADER_LINE_HEIGHT + FRAME_HEADER_MARGIN + FRAME_HEADER_PADDING + 1


AVAILABLE_TEXT_HEIGHT = (
    SLIDE_HEIGHT
    - SLIDE_PADDING_TOP
    - SLIDE_PADDING_BOTTOM
    - BODY_PADDING_VERTICAL
    - _header_height(FRAME_HEADER_LINES)
)

# Paginator uses a conservative budget so Playwright overflow correction peels less.
EFFECTIVE_TEXT_HEIGHT = AVAILABLE_TEXT_HEIGHT * 0.94


def _chars_per_line(font_size: int, content_width: int = CONTENT_WIDTH) -> int:
    return max(1, int(content_width / font_size))


def _line_count(text: str, font_size: int, content_width: int = CONTENT_WIDTH) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    chars_per_line = _chars_per_line(font_size, content_width)
    return max(1, (len(stripped) + chars_per_line - 1) // chars_per_line)


def _code_line_count(text: str, font_size: int, content_width: int = CONTENT_WIDTH) -> int:
    lines = text.strip("\n").splitlines()
    if not lines:
        return 0
    chars_per_line = max(1, int(content_width / (font_size * 0.62)))
    total = 0
    for line in lines:
        visual_chars = max(1, len(line.rstrip()))
        total += max(1, (visual_chars + chars_per_line - 1) // chars_per_line)
    return total


def estimate_block_height(block: ContentBlock) -> float:
    if block.kind == "quote":
        font_size = QUOTE_FONT
        line_height = QUOTE_LINE_HEIGHT
        padding = QUOTE_PADDING_VERTICAL
        content_width = CONTENT_WIDTH - QUOTE_PADDING_HORIZONTAL
    elif block.kind == "code":
        font_size = CODE_FONT
        line_height = CODE_LINE_HEIGHT
        padding = CODE_PADDING_VERTICAL
        content_width = CONTENT_WIDTH - CODE_PADDING_HORIZONTAL
        lines = _code_line_count(block.text, font_size, content_width)
        return lines * font_size * line_height + padding
    else:
        font_size = PARAGRAPH_FONT
        line_height = PARAGRAPH_LINE_HEIGHT
        padding = 0.0
        content_width = CONTENT_WIDTH

    lines = _line_count(block.text, font_size, content_width)
    return lines * font_size * line_height + padding


def page_content_height(blocks: list[ContentBlock]) -> float:
    if not blocks:
        return 0.0

    total = 0.0
    for index, block in enumerate(blocks):
        if index > 0:
            total += BLOCK_GAP
        total += estimate_block_height(block)
    return total


def block_fits_on_page(block: ContentBlock) -> bool:
    return page_content_height([block]) <= AVAILABLE_TEXT_HEIGHT


def page_has_room(page: list[ContentBlock], block: ContentBlock) -> bool:
    if not page:
        return block_fits_on_page(block)
    return page_content_height(page + [block]) <= AVAILABLE_TEXT_HEIGHT
