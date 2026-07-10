"""Correct body slide overflow and underfill using Playwright measurement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from markdown_to_image.browser import launch_browser
from markdown_to_image.parser import ContentBlock
from markdown_to_image.browser_paginator import _BODY_FITS_JS
from markdown_to_image.paginator import (
    _append_flow_piece,
    _page_ends_with_dangling_break,
    _pull_leading_piece,
    continues_same_paragraph,
    split_clauses,
    split_sentences,
)

_VIEWPORT: Any = {"width": 1080, "height": 1440}

_BODY_OVERFLOW_JS = f"""() => !({_BODY_FITS_JS})()"""

_UNDERFILL_SLACK_JS = """() => {
    const body = document.querySelector('.slide-article .slide-body');
    const header = document.querySelector('.frame-header');
    const xTitle = document.querySelector('.x-article-title');
    const textArea = document.querySelector('.slide-article .article-body-text');
    if (!body || !textArea) return { slack: 0, clientHeight: 0 };
    const bodyH = body.clientHeight;
    const headerH = header ? header.scrollHeight : 0;
    const titleH = xTitle ? xTitle.scrollHeight : 0;
    const textH = textArea.scrollHeight;
    const slack = bodyH - headerH - titleH - textH;
    return {
        slack: Math.max(0, slack),
        clientHeight: bodyH
    };
}"""

_UNDERFILL_SLACK_RATIO = 0.05
_MAX_UNDERFILL_PULLS = 12
_MIN_PREFIX_CHARS = 8
_PREFIX_SNAP_SEPARATORS = "，,、；; "
_MAX_PREFIX_PROBE_STEPS = 24
_GREEDY_CHAR_CHUNK = 28


def _peel_last_piece(page: list[ContentBlock]) -> ContentBlock | None:
    if not page:
        return None

    last = page[-1]
    if last.kind == "code":
        lines = last.text.strip("\n").splitlines()
        if len(lines) > 1:
            page[-1] = last.with_text("\n".join(lines[:-1]))
            return last.with_text(lines[-1])
        return page.pop()

    sentences = split_sentences(last.text)
    if len(sentences) > 1:
        moved_text = sentences[-1]
        remainder = "".join(sentences[:-1])
        if remainder.strip():
            page[-1] = last.with_text(remainder)
        else:
            page.pop()
        return last.with_text(moved_text)

    clauses = split_clauses(last.text)
    if len(clauses) > 1:
        moved_text = clauses[-1]
        remainder = "".join(clauses[:-1])
        if remainder.strip():
            page[-1] = last.with_text(remainder)
        else:
            page.pop()
        return last.with_text(moved_text)

    return page.pop()


def _greedy_prefix_units(text: str) -> list[str]:
    clauses = split_clauses(text)
    if len(clauses) > 1:
        return clauses

    units: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + _GREEDY_CHAR_CHUNK)
        if end < len(text):
            snap_at = -1
            for separator in _PREFIX_SNAP_SEPARATORS:
                index = text.rfind(separator, start, end)
                if index >= start + _MIN_PREFIX_CHARS - 1:
                    snap_at = max(snap_at, index + 1)
            if snap_at > start:
                end = snap_at
        units.append(text[start:end])
        start = end
    return units


def _page_overflows(html: str, browser_page: Any) -> bool:
    browser_page.set_content(html, wait_until="load")
    return bool(browser_page.evaluate(_BODY_OVERFLOW_JS))


def _page_underfill_slack(
    html: str,
    browser_page: Any,
    *,
    min_ratio: float = _UNDERFILL_SLACK_RATIO,
) -> float:
    browser_page.set_content(html, wait_until="load")
    metrics = browser_page.evaluate(_UNDERFILL_SLACK_JS)
    if not isinstance(metrics, dict):
        return 0.0
    slack = float(metrics.get("slack") or 0)
    client_height = float(metrics.get("clientHeight") or 0)
    if client_height <= 0:
        return 0.0
    if slack / client_height < min_ratio:
        return 0.0
    return slack


def _try_pull_whole_leading_block(
    page: list[ContentBlock],
    next_page: list[ContentBlock],
    render_page_html: Callable[..., str],
    browser_page: Any,
    probe_total: int,
    page_index: int,
    all_pages: list[list[ContentBlock]],
) -> bool:
    """Move the first next-page block onto page when same paragraph and it fits cleanly."""
    if not continues_same_paragraph(page, next_page):
        return False

    first = next_page[0]
    candidate = list(page)
    _append_flow_piece(candidate, first)
    candidate_html = render_page_html(candidate, probe_total, page_index, all_pages)
    if _page_overflows(candidate_html, browser_page):
        return False

    _append_flow_piece(page, first)
    next_page.pop(0)
    return True


def _pull_max_fit_prefix(
    page: list[ContentBlock],
    next_page: list[ContentBlock],
    render_page_html: Callable[..., str],
    browser_page: Any,
    probe_total: int,
    page_index: int,
    all_pages: list[list[ContentBlock]],
) -> bool:
    if not next_page:
        return False

    first = next_page[0]
    if first.kind == "code":
        return False
    text = first.text.strip()
    if not text:
        return False

    units = _greedy_prefix_units(text)
    using_clauses = len(split_clauses(text)) > 1
    accumulated = ""
    best_raw_len = 0

    for step, unit in enumerate(units):
        if step >= _MAX_PREFIX_PROBE_STEPS:
            break

        trial = f"{accumulated}{unit}"
        trial_prefix = trial.strip()
        if not trial_prefix:
            continue
        if (
            not using_clauses
            and len(trial_prefix) < _MIN_PREFIX_CHARS
            and step + 1 < len(units)
        ):
            accumulated = trial
            continue

        moved = first.with_text(trial_prefix)
        candidate = list(page)
        _append_flow_piece(candidate, moved)
        candidate_html = render_page_html(candidate, probe_total, page_index, all_pages)
        if _page_overflows(candidate_html, browser_page):
            break

        best_raw_len = len(trial)
        accumulated = trial

    if best_raw_len <= 0:
        return False

    best_prefix = text[:best_raw_len].strip()
    remainder = text[best_raw_len:].strip()

    moved = first.with_text(best_prefix)
    _append_flow_piece(page, moved)
    if remainder:
        next_page[0] = first.with_text(remainder)
    else:
        next_page.pop(0)
    return True


def _pull_forward_into_page(
    page: list[ContentBlock],
    next_page: list[ContentBlock],
    render_page_html: Callable[..., str],
    browser_page: Any,
    probe_total: int,
    page_index: int,
    all_pages: list[list[ContentBlock]],
    *,
    allow_prefix_fit: bool = True,
) -> bool:
    if not next_page:
        return False

    if _try_pull_whole_leading_block(
        page,
        next_page,
        render_page_html,
        browser_page,
        probe_total,
        page_index,
        all_pages,
    ):
        return True

    moved, remainder = _pull_leading_piece(next_page[0])
    if moved is not None:
        candidate = list(page)
        _append_flow_piece(candidate, moved)
        probe_next = list(next_page[1:])
        if remainder is not None:
            probe_next.insert(0, remainder)
        candidate_html = render_page_html(candidate, probe_total, page_index, all_pages)
        if not _page_overflows(candidate_html, browser_page):
            _append_flow_piece(page, moved)
            if remainder is not None:
                next_page[0] = remainder
            else:
                next_page.pop(0)
            return True

    if allow_prefix_fit:
        return _pull_max_fit_prefix(
            page, next_page, render_page_html, browser_page, probe_total, page_index, all_pages
        )
    return False


def correct_body_page_underfills(
    pages: list[list[ContentBlock]],
    render_page_html: Callable[..., str],
) -> list[list[ContentBlock]]:
    """Pull leading content from the next slide when the body text area has excess slack."""
    if len(pages) < 2:
        return pages

    from playwright.sync_api import sync_playwright

    balanced = [list(page) for page in pages]
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            browser_page = browser.new_page(viewport=_VIEWPORT)
            index = 0
            while index < len(balanced) - 1:
                if not balanced[index] or not balanced[index + 1]:
                    index += 1
                    continue

                probe_total = len(balanced) + 2
                pull_attempts = 0
                while balanced[index + 1] and pull_attempts < _MAX_UNDERFILL_PULLS:
                    pull_attempts += 1
                    html = render_page_html(balanced[index], probe_total, index, balanced)
                    slack = _page_underfill_slack(html, browser_page, min_ratio=0.0)
                    if slack <= 0:
                        break

                    pulled = _pull_forward_into_page(
                        balanced[index],
                        balanced[index + 1],
                        render_page_html,
                        browser_page,
                        probe_total,
                        index,
                        balanced,
                        allow_prefix_fit=False,
                    )
                    if not pulled:
                        pulled = _pull_forward_into_page(
                            balanced[index],
                            balanced[index + 1],
                            render_page_html,
                            browser_page,
                            probe_total,
                            index,
                            balanced,
                            allow_prefix_fit=True,
                        )
                    if not pulled:
                        break

                    if not balanced[index + 1]:
                        balanced.pop(index + 1)
                        break

                index += 1

            browser_page.close()
        finally:
            browser.close()

    return [page for page in balanced if page]


def correct_body_page_overflows(
    pages: list[list[ContentBlock]],
    render_page_html: Callable[..., str],
) -> list[list[ContentBlock]]:
    """Peel trailing content only from slides that overflow in Chromium."""
    if not pages:
        return pages

    from playwright.sync_api import sync_playwright

    corrected = [list(page) for page in pages]
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            browser_page = browser.new_page(viewport=_VIEWPORT)
            index = 0
            while index < len(corrected):
                if not corrected[index]:
                    corrected.pop(index)
                    continue

                probe_total = len(corrected) + 2
                html = render_page_html(corrected[index], probe_total, index, corrected)
                if not _page_overflows(html, browser_page):
                    index += 1
                    continue

                moved = _peel_last_piece(corrected[index])
                if moved is None:
                    index += 1
                    continue

                if index + 1 < len(corrected):
                    corrected[index + 1].insert(0, moved)
                else:
                    corrected.append([moved])

            browser_page.close()
        finally:
            browser.close()

    return [page for page in corrected if page]
