"""Paginate article content blocks into slide pages."""

from __future__ import annotations

from markdown_to_image.layout import (
    AVAILABLE_TEXT_HEIGHT,
    DEFAULT_SPLIT_CHARS,
    EFFECTIVE_TEXT_HEIGHT,
    estimate_block_height,
    page_content_height,
)
from markdown_to_image.parser import ContentBlock

_ORPHAN_LEAD_MAX_CHARS = 36
_MIN_PAGE_FILL_RATIO = 0.88
_MIN_FRAGMENT_CHARS = 4
_CLAUSE_SEPARATORS = "，,"
_FLOW_END_PUNCT = "，,、；;：:"
_CODE_CHAR_WEIGHT = 0.55
_CODE_SPLIT_OVERAGE = 1.2
_MIN_CODE_LINE_CHARS = 80


def char_count(text: str) -> int:
    return len(text.strip())


def _code_char_count(text: str) -> int:
    return max(1, int(len(text.strip()) * _CODE_CHAR_WEIGHT))


def block_char_count(block: ContentBlock) -> int:
    if block.kind == "code":
        return _code_char_count(block.text)
    return char_count(block.text)


def split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    sentences: list[str] = []
    depth = 0
    buffer = ""
    for char in stripped:
        buffer += char
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
        elif char in "。！？；" and depth == 0:
            sentences.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        sentences.append(buffer.strip())
    return sentences


def split_clauses(text: str) -> list[str]:
    """Split on Chinese/ASCII commas for book-style mid-sentence page breaks."""
    stripped = text.strip()
    if not stripped:
        return []

    clauses: list[str] = []
    depth = 0
    buffer = ""
    for char in stripped:
        buffer += char
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
        elif char in _CLAUSE_SEPARATORS and depth == 0:
            clauses.append(buffer)
            buffer = ""
    if buffer.strip():
        clauses.append(buffer)
    if len(clauses) <= 1:
        return [stripped]
    return clauses


def hard_split_text(text: str, max_chars: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if char_count(stripped) <= max_chars:
        return [stripped]
    parts: list[str] = []
    start = 0
    while start < len(stripped):
        chunk = stripped[start : start + max_chars].strip()
        if chunk:
            parts.append(chunk)
        start += max_chars
    return parts


def _max_code_line_chars(max_chars: int) -> int:
    return max(_MIN_CODE_LINE_CHARS, int(max_chars / _CODE_CHAR_WEIGHT))


def _split_long_code_line(line: str, max_chars: int) -> list[str]:
    if _code_char_count(line) <= max_chars:
        return [line]

    limit = _max_code_line_chars(max_chars)
    min_snap = max(24, int(limit * 0.55))
    chunks: list[str] = []
    start = 0
    while start < len(line):
        end = min(len(line), start + limit)
        if end < len(line):
            snap_at = -1
            for separator in (" ", "\t", "/", "&", "?", "=", ",", ";", "|", "-"):
                index = line.rfind(separator, start + min_snap, end)
                if index >= start + min_snap:
                    snap_at = max(snap_at, index + 1)
            if snap_at > start:
                end = snap_at

        chunk = line[start:end]
        if chunk:
            chunks.append(chunk)
        start = max(end, start + 1)

    return chunks


def _split_oversized_code_unit(unit: list[str], max_chars: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_count = 0

    for line in unit:
        for line_piece in _split_long_code_line(line, max_chars):
            piece_count = _code_char_count(line_piece)
            if current and current_count + piece_count > max_chars:
                chunks.append(current)
                current = []
                current_count = 0
            current.append(line_piece)
            current_count += piece_count

    if current:
        chunks.append(current)
    return chunks


def _code_unit_needs_split(text: str, max_chars: int) -> bool:
    return _code_char_count(text) > int(max_chars * _CODE_SPLIT_OVERAGE)


def split_code_lines(text: str, max_chars: int) -> list[str]:
    lines = text.strip("\n").splitlines()
    if not lines:
        return []

    units: list[list[str]] = []
    current_unit: list[str] = []
    for line in lines:
        stripped = line.strip()
        starts_named_group = stripped.startswith("#") and bool(current_unit)
        if starts_named_group:
            units.append(current_unit)
            current_unit = []
        current_unit.append(line)
    if current_unit:
        units.append(current_unit)

    split_units: list[list[str]] = []
    for unit in units:
        unit_text = "\n".join(unit)
        if _code_unit_needs_split(unit_text, max_chars):
            split_units.extend(_split_oversized_code_unit(unit, max_chars))
        else:
            split_units.append(unit)

    parts: list[str] = []
    current: list[str] = []
    current_count = 0
    for unit in split_units:
        unit_text = "\n".join(unit)
        unit_count = _code_char_count(unit_text)
        if current and current_count + unit_count > max_chars:
            parts.append("\n".join(current))
            current = []
            current_count = 0
        current.extend(unit)
        current_count += unit_count

    if current:
        parts.append("\n".join(current))
    return [part for part in parts if part.strip()]


def iter_text_pieces(text: str, max_chars: int) -> list[str]:
    if char_count(text) <= max_chars:
        return [text.strip()]

    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return hard_split_text(text, max_chars)

    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if char_count(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(hard_split_text(sentence, max_chars))
            continue

        candidate = f"{current}{sentence}" if current else sentence
        if char_count(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = sentence

    if current.strip():
        pieces.append(current.strip())
    return pieces


def _clone_block(block: ContentBlock, text: str) -> ContentBlock:
    return block.with_text(text)


def _join_block_text(left: ContentBlock, right: ContentBlock) -> str:
    if left.kind == "code":
        return f"{left.text.rstrip()}\n{right.text.lstrip()}".strip("\n")
    return left.text + right.text


def _can_merge_blocks(left: ContentBlock, right: ContentBlock) -> bool:
    return left.kind == right.kind and left.source_id == right.source_id


def continues_same_paragraph(page: list[ContentBlock], next_page: list[ContentBlock]) -> bool:
    """True when the next slide continues the same markdown paragraph."""
    if not page or not next_page:
        return False
    last = page[-1]
    first = next_page[0]
    return (
        last.kind == "paragraph"
        and first.kind == "paragraph"
        and last.source_id == first.source_id
    )


def split_block_to_chunks(block: ContentBlock, max_chars: int) -> list[ContentBlock]:
    if block_char_count(block) <= max_chars:
        return [block]
    if block.kind == "code":
        return [_clone_block(block, piece) for piece in split_code_lines(block.text, max_chars)]
    return [_clone_block(block, piece) for piece in iter_text_pieces(block.text, max_chars)]


def _probe_page_with_piece(page: list[ContentBlock], piece: ContentBlock) -> list[ContentBlock]:
    probe = list(page)
    if probe and _can_merge_blocks(probe[-1], piece):
        probe[-1] = _clone_block(probe[-1], _join_block_text(probe[-1], piece))
    else:
        probe.append(piece)
    return probe


def _can_append_flow_piece(page: list[ContentBlock], piece: ContentBlock) -> bool:
    if not page:
        return estimate_block_height(piece) <= EFFECTIVE_TEXT_HEIGHT
    probe = _probe_page_with_piece(page, piece)
    return page_content_height(probe) <= EFFECTIVE_TEXT_HEIGHT


def _append_flow_piece(page: list[ContentBlock], piece: ContentBlock) -> None:
    if page and _can_merge_blocks(page[-1], piece):
        page[-1] = _clone_block(page[-1], _join_block_text(page[-1], piece))
        return
    page.append(piece)


def _expand_block_to_flow_pieces(block: ContentBlock, max_chars: int) -> list[ContentBlock]:
    text = block.text.strip()
    if not text:
        return []

    if block.kind == "code":
        if page_content_height([block]) <= EFFECTIVE_TEXT_HEIGHT and block_char_count(block) <= max_chars:
            return [block]
        return split_block_to_chunks(block, max_chars)

    if page_content_height([block]) <= EFFECTIVE_TEXT_HEIGHT:
        sentences = split_sentences(text)
        if len(sentences) <= 1:
            return [block]
        return [_clone_block(block, sentence) for sentence in sentences]

    pieces: list[ContentBlock] = []
    for piece in iter_text_pieces(text, max_chars):
        chunk = _clone_block(block, piece)
        if page_content_height([chunk]) <= EFFECTIVE_TEXT_HEIGHT:
            for sentence in split_sentences(piece):
                pieces.append(_clone_block(block, sentence))
            continue
        pieces.extend(split_block_to_chunks(chunk, max(80, max_chars // 2)))
    return pieces


def _is_tiny_fragment(block: ContentBlock) -> bool:
    text = block.text.strip()
    return char_count(text) < _MIN_FRAGMENT_CHARS


def _merge_adjacent_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    if not blocks:
        return []

    merged: list[ContentBlock] = []
    for block in blocks:
        if merged and _can_merge_blocks(merged[-1], block):
            merged[-1] = _clone_block(merged[-1], _join_block_text(merged[-1], block))
            continue
        merged.append(block)

    normalized: list[ContentBlock] = []
    for block in merged:
        if block.kind != "paragraph":
            normalized.append(block)
            continue

        sentences = split_sentences(block.text)
        trailing_orphans: list[str] = []
        while sentences and _is_orphan_lead(ContentBlock("paragraph", sentences[-1])):
            trailing_orphans.insert(0, sentences.pop())

        if sentences:
            normalized.append(_clone_block(block, "".join(sentences)))
        for orphan in trailing_orphans:
            normalized.append(_clone_block(block, orphan))

    return normalized


def _merge_page_fragments(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    for index, page in enumerate(pages):
        if not page:
            continue
        cleaned: list[ContentBlock] = []
        for block in page:
            if cleaned and _is_tiny_fragment(block) and _can_merge_blocks(cleaned[-1], block):
                prev = cleaned[-1]
                cleaned[-1] = _clone_block(prev, _join_block_text(prev, block))
                continue
            if _is_tiny_fragment(block) and index + 1 < len(pages) and pages[index + 1]:
                nxt = pages[index + 1][0]
                if _can_merge_blocks(block, nxt):
                    pages[index + 1][0] = _clone_block(nxt, _join_block_text(block, nxt))
                    continue
            cleaned.append(block)
        pages[index] = cleaned
    return [page for page in pages if page]


def _is_orphan_lead(block: ContentBlock) -> bool:
    if block.kind != "paragraph":
        return False
    text = block.text.strip()
    return text.endswith("：") and char_count(text) <= _ORPHAN_LEAD_MAX_CHARS


def _page_fill_ratio(page: list[ContentBlock]) -> float:
    if not page or EFFECTIVE_TEXT_HEIGHT <= 0:
        return 0.0
    return page_content_height(page) / EFFECTIVE_TEXT_HEIGHT


def _pull_leading_piece(block: ContentBlock) -> tuple[ContentBlock | None, ContentBlock | None]:
    """Take the leading sentence or clause from a block, leaving the remainder on the slide."""
    text = block.text.strip()
    if not text:
        return None, None

    if block.kind == "code":
        pieces = split_code_lines(text, max(80, DEFAULT_SPLIT_CHARS // 2))
        if len(pieces) > 1:
            return _clone_block(block, pieces[0]), _clone_block(block, "\n".join(pieces[1:]))
        return _clone_block(block, text), None

    sentences = split_sentences(text)
    if len(sentences) > 1:
        moved_text = sentences[0]
        remainder = "".join(sentences[1:])
        return (
            _clone_block(block, moved_text),
            _clone_block(block, remainder) if remainder.strip() else None,
        )

    clauses = split_clauses(text)
    if len(clauses) > 1:
        moved_text = clauses[0]
        remainder = "".join(clauses[1:])
        return (
            _clone_block(block, moved_text),
            _clone_block(block, remainder) if remainder.strip() else None,
        )

    return _clone_block(block, text), None


def _try_backfill_piece(
    current: list[ContentBlock],
    next_page: list[ContentBlock],
    *,
    allow_sparse_next: bool,
    min_height: float,
) -> bool:
    if not next_page:
        return False

    first = next_page[0]
    if _is_orphan_lead(first) and len(next_page) > 1:
        return False

    if continues_same_paragraph(current, next_page) and _can_append_flow_piece(current, first):
        probe_current = _probe_page_with_piece(current, first)
        remaining_next = list(next_page[1:])
        if not allow_sparse_next and remaining_next and page_content_height(remaining_next) < min_height:
            pass
        else:
            _append_flow_piece(current, first)
            next_page.pop(0)
            return True

    moved, remainder = _pull_leading_piece(first)
    if moved is None:
        return False

    remaining_next = list(next_page[1:])
    if remainder is not None:
        remaining_next.insert(0, remainder)

    if not allow_sparse_next and remaining_next and page_content_height(remaining_next) < min_height:
        return False
    if not _can_append_flow_piece(current, moved):
        return False

    probe_current = _probe_page_with_piece(current, moved)
    probe_next = list(next_page[1:])
    if remainder is not None:
        probe_next.insert(0, remainder)

    _append_flow_piece(current, moved)
    if remainder is not None:
        next_page[0] = remainder
    else:
        next_page.pop(0)
    return True


def _ends_with_flow_punctuation(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in _FLOW_END_PUNCT


def _page_ends_with_dangling_break(page: list[ContentBlock], next_page: list[ContentBlock]) -> bool:
    """True when the page ends mid-sentence (comma) continuing into the next page."""
    if not page or not next_page:
        return False
    last = page[-1]
    first = next_page[0]
    if not _can_merge_blocks(last, first):
        return False
    return _ends_with_flow_punctuation(last.text)


def _fix_dangling_page_breaks(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    """Peel trailing clauses to the next slide so pages do not end on a comma."""
    if len(pages) <= 1:
        return pages

    changed = True
    while changed:
        changed = False
        for index in range(len(pages) - 1):
            page = pages[index]
            nxt = pages[index + 1]
            if not _page_ends_with_dangling_break(page, nxt):
                continue

            last = page[-1]
            clauses = split_clauses(last.text)
            if len(clauses) <= 1:
                nxt.insert(0, page.pop())
                changed = True
                continue

            peeled_text = clauses.pop()
            remainder = "".join(clauses)
            if remainder.strip():
                page[-1] = _clone_block(last, remainder)
            else:
                page.pop()

            peeled = _clone_block(last, peeled_text)
            if nxt and _can_merge_blocks(peeled, nxt[0]):
                nxt[0] = _clone_block(peeled, _join_block_text(peeled, nxt[0]))
            else:
                nxt.insert(0, peeled)
            changed = True

    return [page for page in pages if page]


def _fix_orphan_leads(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    if len(pages) <= 1:
        return pages

    changed = True
    while changed:
        changed = False
        for index in range(len(pages) - 1):
            page = pages[index]
            if not page or not _is_orphan_lead(page[-1]):
                continue
            pages[index + 1].insert(0, page.pop())
            changed = True

    return [page for page in pages if page]


def _backfill_sparse_pages(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    min_height = EFFECTIVE_TEXT_HEIGHT * _MIN_PAGE_FILL_RATIO
    index = 0
    while index < len(pages) - 1:
        while index < len(pages) - 1:
            current = pages[index]
            next_page = pages[index + 1]
            if not next_page:
                break
            if _page_fill_ratio(current) >= _MIN_PAGE_FILL_RATIO:
                break

            allow_sparse_next = index + 1 == len(pages) - 1
            if not _try_backfill_piece(
                current,
                next_page,
                allow_sparse_next=allow_sparse_next,
                min_height=min_height,
            ):
                break

            if not next_page:
                pages.pop(index + 1)

        index += 1

    return [page for page in pages if page]


def _maybe_merge_tail_page(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    """Merge the last page into the previous one only when the combined page fits."""
    if len(pages) < 2:
        return pages

    tail = pages[-1]
    previous = pages[-2]
    if not previous or not tail:
        return pages

    combined = previous + tail
    if page_content_height(combined) <= EFFECTIVE_TEXT_HEIGHT:
        pages[-2] = combined
        pages.pop()
    return pages


def _merge_sparse_adjacent_pages(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    """Merge consecutive slides when both are under-filled and the union still fits."""
    min_height = EFFECTIVE_TEXT_HEIGHT * _MIN_PAGE_FILL_RATIO
    changed = True
    while changed:
        changed = False
        index = 0
        while index < len(pages) - 1:
            current = pages[index]
            nxt = pages[index + 1]
            if not current or not nxt:
                index += 1
                continue

            current_height = page_content_height(current)
            next_height = page_content_height(nxt)
            if current_height >= min_height and next_height >= min_height:
                index += 1
                continue

            combined = current + nxt
            if page_content_height(combined) > EFFECTIVE_TEXT_HEIGHT:
                index += 1
                continue

            pages[index] = _merge_adjacent_blocks(combined)
            pages.pop(index + 1)
            changed = True

    return pages


def _rebalance_pages(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    for _ in range(max(len(pages), 1) * 2):
        snapshot = [tuple(block.text for block in page) for page in pages]
        pages = _backfill_sparse_pages(pages)
        pages = _merge_sparse_adjacent_pages(pages)
        pages = _maybe_merge_tail_page(pages)
        if [tuple(block.text for block in page) for page in pages] == snapshot:
            break
    return pages


def paginate_blocks(blocks: list[ContentBlock], max_chars: int = 340) -> list[list[ContentBlock]]:
    """Fill slides book-style: sentence flow, backfill sparse pages from the next."""
    stream: list[ContentBlock] = []
    for source_id, block in enumerate(blocks):
        for piece in _expand_block_to_flow_pieces(block, max_chars):
            stream.append(piece.with_text(piece.text, source_id))

    pages: list[list[ContentBlock]] = []
    current_page: list[ContentBlock] = []

    for piece in stream:
        if current_page and not _can_append_flow_piece(current_page, piece):
            pages.append(_merge_adjacent_blocks(current_page))
            current_page = [piece]
            continue
        _append_flow_piece(current_page, piece)

    if current_page:
        pages.append(_merge_adjacent_blocks(current_page))

    pages = _fix_orphan_leads(pages)
    pages = _rebalance_pages(pages)
    pages = _fix_dangling_page_breaks(pages)
    pages = _fix_orphan_leads(pages)
    pages = _merge_page_fragments(pages)
    pages = _fix_orphan_leads(pages)
    return [_merge_adjacent_blocks(page) for page in pages if page]


def balance_body_pages(pages: list[list[ContentBlock]]) -> list[list[ContentBlock]]:
    """Estimate-based backfill after initial pagination; fills slides before overflow correction."""
    if not pages:
        return pages
    balanced = [list(page) for page in pages]
    balanced = _backfill_sparse_pages(balanced)
    balanced = _fix_dangling_page_breaks(balanced)
    return [_merge_adjacent_blocks(page) for page in balanced if page]
