"""Browser-measured pagination for article body slides."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from markdown_to_image.browser import launch_browser
from markdown_to_image.parser import ContentBlock
from markdown_to_image.paginator import (
    _merge_adjacent_blocks,
    iter_text_pieces,
    split_clauses,
    split_sentences,
)

_VIEWPORT: Any = {"width": 1080, "height": 1440}
_FLOW_END_PUNCT = "，,、；;：:"
_CLOSING_PUNCT = "。！？!?）)]》」』”’"
_MIN_FRAGMENT_CHARS = 8
_CHAR_CHUNK = 28
_MAX_CLEANUP_PASSES = 3
_FIT_TOLERANCE_PX = 2
_UNBOUNDED_CHAR_LIMIT = 1_000_000_000

_BODY_FITS_JS = f"""() => {{
    const textArea = document.querySelector('.slide-article .article-body-text');
    const body = document.querySelector('.slide-article .slide-body');
    if (!textArea || !body) return false;

    const blocks = Array.from(textArea.children);
    if (blocks.length === 0) return true;

    const bodyRect = body.getBoundingClientRect();
    const bodyStyle = getComputedStyle(body);
    const paddingTop = parseFloat(bodyStyle.paddingTop) || 0;
    const paddingBottom = parseFloat(bodyStyle.paddingBottom) || 0;
    const safeTop = bodyRect.top + paddingTop;
    const safeBottom = bodyRect.bottom - paddingBottom;
    const firstRect = blocks[0].getBoundingClientRect();
    const lastRect = blocks[blocks.length - 1].getBoundingClientRect();

    return (
        firstRect.top >= safeTop - {_FIT_TOLERANCE_PX}
        && lastRect.bottom <= safeBottom + {_FIT_TOLERANCE_PX}
    );
}}"""

RenderPageHtml = Callable[[list[ContentBlock], int, int, list[list[ContentBlock]] | None], str]


def _clone(block: ContentBlock, text: str) -> ContentBlock:
    return ContentBlock(block.kind, text, block.source_id)


def _same_source(left: ContentBlock, right: ContentBlock) -> bool:
    return left.kind == right.kind and left.source_id == right.source_id


def _normalize_sources(blocks: list[ContentBlock]) -> list[ContentBlock]:
    return [
        ContentBlock(block.kind, block.text.strip(), index)
        for index, block in enumerate(blocks)
        if block.text.strip()
    ]


def _page_char_count(page: list[ContentBlock]) -> int:
    return len("".join(block.text.strip() for block in _merge_adjacent_blocks(page)))


def _within_char_limit(page: list[ContentBlock], max_chars: int) -> bool:
    return _page_char_count(page) <= max_chars


def _page_with_piece(page: list[ContentBlock], piece: ContentBlock) -> list[ContentBlock]:
    probe = list(page)
    if probe and _same_source(probe[-1], piece):
        probe[-1] = _clone(probe[-1], probe[-1].text + piece.text)
    else:
        probe.append(piece)
    return probe


def _snapshot_with_page(
    pages: list[list[ContentBlock]],
    page_index: int,
    candidate: list[ContentBlock],
) -> list[list[ContentBlock]]:
    snapshot = [list(page) for page in pages]
    if page_index < len(snapshot):
        snapshot[page_index] = candidate
    else:
        snapshot.append(candidate)
    return snapshot


def _page_fits(
    page: list[ContentBlock],
    page_index: int,
    pages: list[list[ContentBlock]],
    render_page_html: RenderPageHtml,
    browser_page: Any,
) -> bool:
    snapshot = _snapshot_with_page(pages, page_index, page)
    html = render_page_html(page, max(len(snapshot), 1), page_index, snapshot)
    browser_page.set_content(html, wait_until="load")
    return bool(browser_page.evaluate(_BODY_FITS_JS))


def _split_leading_chars(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if len(stripped) <= _MIN_FRAGMENT_CHARS:
        return None
    end = min(len(stripped), _CHAR_CHUNK)
    if end < len(stripped):
        snap_at = -1
        for separator in "，,、；; ":
            index = stripped.rfind(separator, _MIN_FRAGMENT_CHARS, end)
            if index >= _MIN_FRAGMENT_CHARS:
                snap_at = max(snap_at, index + 1)
        if snap_at > _MIN_FRAGMENT_CHARS:
            end = snap_at
    return stripped[:end].strip(), stripped[end:].strip()


def _split_first_sentence(block: ContentBlock) -> tuple[ContentBlock, ContentBlock] | None:
    sentences = split_sentences(block.text)
    if len(sentences) <= 1:
        return None
    moved = sentences[0]
    remainder = "".join(sentences[1:]).strip()
    if not remainder:
        return None
    return _clone(block, moved), _clone(block, remainder)


def _split_first_clause(block: ContentBlock) -> tuple[ContentBlock, ContentBlock] | None:
    clauses = split_clauses(block.text)
    if len(clauses) <= 1:
        return None
    moved = clauses[0]
    remainder = "".join(clauses[1:]).strip()
    if not remainder:
        return None
    return _clone(block, moved), _clone(block, remainder)


def _split_first_chunk(block: ContentBlock) -> tuple[ContentBlock, ContentBlock] | None:
    split = _split_leading_chars(block.text)
    if split is None:
        return None
    moved, remainder = split
    if not moved or not remainder:
        return None
    return _clone(block, moved), _clone(block, remainder)


def _leading_splits(block: ContentBlock) -> list[tuple[ContentBlock, ContentBlock]]:
    splits: list[tuple[ContentBlock, ContentBlock]] = []
    for splitter in (_split_first_sentence, _split_first_clause, _split_first_chunk):
        split = splitter(block)
        if split is not None:
            moved, remainder = split
            if moved.text and remainder.text:
                splits.append(split)
    return splits


def _split_unit(block: ContentBlock, max_chars: int) -> list[ContentBlock]:
    pieces = iter_text_pieces(block.text, max_chars)
    if len(pieces) > 1:
        return [_clone(block, piece) for piece in pieces if piece.strip()]

    sentences = split_sentences(block.text)
    if len(sentences) > 1:
        return [_clone(block, sentence) for sentence in sentences if sentence.strip()]

    clauses = split_clauses(block.text)
    if len(clauses) > 1:
        return [_clone(block, clause) for clause in clauses if clause.strip()]

    chunks: list[ContentBlock] = []
    remainder = block
    while True:
        split = _split_first_chunk(remainder)
        if split is None:
            break
        moved, remainder = split
        chunks.append(moved)
    if remainder.text.strip():
        chunks.append(remainder)
    return chunks if len(chunks) > 1 else [block]


def _try_place_leading_piece(
    current: list[ContentBlock],
    unit: ContentBlock,
    pages: list[list[ContentBlock]],
    render_page_html: RenderPageHtml,
    browser_page: Any,
    max_chars: int,
) -> tuple[list[ContentBlock], ContentBlock] | None:
    page_index = len(pages)
    for moved, remainder in _leading_splits(unit):
        candidate = _page_with_piece(current, moved)
        if _within_char_limit(candidate, max_chars) and _page_fits(
            candidate,
            page_index,
            pages,
            render_page_html,
            browser_page,
        ):
            return candidate, remainder
    return None


def _tail_is_bad(page: list[ContentBlock], next_page: list[ContentBlock]) -> bool:
    if not page or not next_page:
        return False
    last = page[-1]
    if last.kind != "paragraph":
        return False
    text = last.text.rstrip()
    if not text:
        return False
    if text[-1] in _FLOW_END_PUNCT:
        return True
    return (
        len(text) < _MIN_FRAGMENT_CHARS
        and next_page[0].kind == last.kind
        and next_page[0].source_id == last.source_id
    )


def _peel_trailing_piece(block: ContentBlock) -> tuple[ContentBlock | None, ContentBlock]:
    sentences = split_sentences(block.text)
    if len(sentences) > 1:
        remainder = "".join(sentences[:-1]).strip()
        moved = sentences[-1].strip()
        if remainder and moved:
            return _clone(block, remainder), _clone(block, moved)

    clauses = split_clauses(block.text)
    if len(clauses) > 1:
        remainder = "".join(clauses[:-1]).strip()
        moved = clauses[-1].strip()
        if remainder and moved:
            return _clone(block, remainder), _clone(block, moved)

    return None, block


def _prepend_piece(page: list[ContentBlock], piece: ContentBlock) -> list[ContentBlock]:
    if page and _same_source(piece, page[0]):
        return [_clone(piece, piece.text + page[0].text), *page[1:]]
    return [piece, *page]


def _pull_prefix_from_next(
    page: list[ContentBlock],
    next_page: list[ContentBlock],
    pages: list[list[ContentBlock]],
    index: int,
    render_page_html: RenderPageHtml,
    browser_page: Any,
    max_chars: int,
) -> tuple[list[ContentBlock], list[ContentBlock]] | None:
    if not next_page:
        return None

    first = next_page[0]
    text = first.text
    best: tuple[list[ContentBlock], list[ContentBlock]] | None = None
    max_end = min(len(text), _CHAR_CHUNK)
    for raw_end in range(1, max_end + 1):
        end = raw_end
        while end < len(text) and text[end] in _CLOSING_PUNCT:
            end += 1
        prefix_text = text[:end]
        if not prefix_text or prefix_text[-1] in _FLOW_END_PUNCT:
            continue
        remainder_text = text[end:]
        prefix = _clone(first, prefix_text)
        candidate_current = _page_with_piece(page, prefix)
        if remainder_text:
            candidate_next = [_clone(first, remainder_text), *next_page[1:]]
        else:
            candidate_next = list(next_page[1:])

        snapshot = [list(p) for p in pages]
        snapshot[index] = candidate_current
        snapshot[index + 1] = candidate_next
        if _within_char_limit(candidate_current, max_chars) and _page_fits(
            candidate_current,
            index,
            snapshot,
            render_page_html,
            browser_page,
        ):
            best = (candidate_current, candidate_next)
    return best


def _cleanup_page_endings(
    pages: list[list[ContentBlock]],
    render_page_html: RenderPageHtml,
    browser_page: Any,
    max_chars: int,
) -> list[list[ContentBlock]]:
    cleaned = [list(page) for page in pages if page]
    for _ in range(_MAX_CLEANUP_PASSES):
        changed = False
        for index in range(len(cleaned) - 1):
            page = cleaned[index]
            next_page = cleaned[index + 1]
            pulled = _pull_prefix_from_next(
                page,
                next_page,
                cleaned,
                index,
                render_page_html,
                browser_page,
                max_chars,
            )
            if pulled is not None:
                cleaned[index], cleaned[index + 1] = pulled
                changed = True
                continue

            if not _tail_is_bad(page, next_page):
                continue

            remainder, moved = _peel_trailing_piece(page[-1])
            if remainder is None and len(page) <= 1:
                continue

            candidate_current = list(page[:-1])
            if remainder is not None:
                candidate_current.append(remainder)
            candidate_next = _prepend_piece(next_page, moved)

            snapshot = [list(p) for p in cleaned]
            snapshot[index] = candidate_current
            snapshot[index + 1] = candidate_next
            if not (
                _within_char_limit(candidate_current, max_chars)
                and _within_char_limit(candidate_next, max_chars)
            ):
                continue

            current_fits = _page_fits(
                candidate_current,
                index,
                snapshot,
                render_page_html,
                browser_page,
            )
            next_fits = _page_fits(
                candidate_next,
                index + 1,
                snapshot,
                render_page_html,
                browser_page,
            )
            if current_fits and next_fits:
                cleaned[index] = candidate_current
                cleaned[index + 1] = candidate_next
                changed = True
        if not changed:
            break
    return [page for page in cleaned if page]


def _verify_pages_fit(
    pages: list[list[ContentBlock]],
    render_page_html: RenderPageHtml,
    browser_page: Any,
    max_chars: int,
) -> None:
    for index, page in enumerate(pages):
        if not _within_char_limit(page, max_chars):
            preview = "".join(block.text for block in page)[:80]
            raise ValueError(
                f"Browser pagination exceeded chars_per_slide on body page {index + 1}: {preview}"
            )
        if not _page_fits(page, index, pages, render_page_html, browser_page):
            preview = "".join(block.text for block in page)[:80]
            raise ValueError(f"Browser pagination produced overflowing body page {index + 1}: {preview}")


def cleanup_page_endings_with_browser(
    pages: list[list[ContentBlock]],
    render_page_html: RenderPageHtml,
    *,
    max_chars: int | None = None,
) -> list[list[ContentBlock]]:
    """Clean dangling page endings after later balancing has moved content between slides."""
    if len(pages) < 2:
        return pages

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Article browser cleanup requires Playwright. "
            "Run `pip install -r scripts/requirements.txt` from the repo root."
        ) from exc

    char_limit = max_chars if max_chars is not None else _UNBOUNDED_CHAR_LIMIT
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            browser_page = browser.new_page(viewport=_VIEWPORT)
            cleaned = _cleanup_page_endings(pages, render_page_html, browser_page, char_limit)
            cleaned = [_merge_adjacent_blocks(page) for page in cleaned if page]
            _verify_pages_fit(cleaned, render_page_html, browser_page, char_limit)
            browser_page.close()
        finally:
            browser.close()

    return cleaned


def paginate_blocks_with_browser(
    blocks: list[ContentBlock],
    render_page_html: RenderPageHtml,
    *,
    max_chars: int = 340,
) -> list[list[ContentBlock]]:
    """Paginate body blocks by asking Chromium whether each candidate page fits."""
    max_chars = max(int(max_chars), _MIN_FRAGMENT_CHARS)

    normalized = _normalize_sources(blocks)
    if not normalized:
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Article browser pagination requires Playwright. "
            "Run `pip install -r scripts/requirements.txt` from the repo root."
        ) from exc

    pages: list[list[ContentBlock]] = []
    current: list[ContentBlock] = []
    queue = list(normalized)

    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            browser_page = browser.new_page(viewport=_VIEWPORT)
            while queue:
                unit = queue.pop(0)
                candidate = _page_with_piece(current, unit)
                if _within_char_limit(candidate, max_chars) and _page_fits(
                    candidate,
                    len(pages),
                    pages,
                    render_page_html,
                    browser_page,
                ):
                    current = candidate
                    continue

                if current:
                    leading = _try_place_leading_piece(
                        current,
                        unit,
                        pages,
                        render_page_html,
                        browser_page,
                        max_chars,
                    )
                    if leading is not None:
                        current, remainder = leading
                        queue.insert(0, remainder)
                        continue

                    pages.append(_merge_adjacent_blocks(current))
                    current = []
                    queue.insert(0, unit)
                    continue

                split_units = _split_unit(unit, max_chars)
                if len(split_units) <= 1:
                    preview = unit.text[:80]
                    raise ValueError(f"Text unit cannot fit on an empty body slide: {preview}")
                queue = split_units + queue

            if current:
                pages.append(_merge_adjacent_blocks(current))

            pages = _cleanup_page_endings(pages, render_page_html, browser_page, max_chars)
            pages = [_merge_adjacent_blocks(page) for page in pages if page]
            _verify_pages_fit(pages, render_page_html, browser_page, max_chars)
            browser_page.close()
        finally:
            browser.close()

    return pages
