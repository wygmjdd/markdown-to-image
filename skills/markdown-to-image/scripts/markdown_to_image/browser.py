"""Shared Playwright browser launch helpers."""

from __future__ import annotations

from typing import Any


PLAYWRIGHT_INSTALL_HINT = (
    "Playwright Chromium is not installed. System Chrome is intentionally not used. "
    "Run:\n"
    "  python -m pip install -r requirements.txt\n"
    "  python -m playwright install chromium"
)
COVER_TITLE_MAX_LINES = 2
COVER_TITLE_MIN_FONT_SIZE = 74

_FIT_COVER_TITLE_JS = r"""
async ({ maxLines, minFontSize }) => {
  const title = document.querySelector('.cover-title');
  if (!title) return null;

  await document.fonts.ready;

  const measureLines = () => {
    const measured = new Map();
    const walker = document.createTreeWalker(title, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      let offset = 0;
      while (offset < node.length) {
        const codePoint = node.data.codePointAt(offset);
        const nextOffset = offset + (codePoint > 0xFFFF ? 2 : 1);
        const range = document.createRange();
        range.setStart(node, offset);
        range.setEnd(node, nextOffset);
        const rect = range.getBoundingClientRect();
        if (rect.width || rect.height) {
          const top = Math.round(rect.top);
          measured.set(
            top,
            (measured.get(top) || '') + node.data.slice(offset, nextOffset),
          );
        }
        offset = nextOffset;
      }
      node = walker.nextNode();
    }
    return [...measured.entries()]
      .sort((left, right) => left[0] - right[0])
      .map((entry) => entry[1].trim());
  };

  const initialFontSize = Number.parseFloat(getComputedStyle(title).fontSize);
  let fontSize = initialFontSize;
  let lines = measureLines();
  while (lines.length > maxLines && fontSize > minFontSize) {
    fontSize = Math.max(minFontSize, fontSize - 1);
    title.style.fontSize = `${fontSize}px`;
    lines = measureLines();
  }

  const lastLine = lines.at(-1) || '';
  return {
    initialFontSize,
    fontSize,
    lineCount: lines.length,
    lines,
    lastLineLength: [...lastLine.replace(/\s/g, '')].length,
  };
}
"""


def launch_browser(playwright: Any) -> Any:
    """Launch Playwright Chromium without touching the user's system Chrome."""
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as error:
        message = str(error)
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from error
        raise


def fit_cover_title(
    browser_page: Any,
    *,
    max_lines: int = COVER_TITLE_MAX_LINES,
    min_font_size: int = COVER_TITLE_MIN_FONT_SIZE,
) -> dict[str, Any] | None:
    """Shrink a rendered cover title until it fits the preferred line count."""
    result = browser_page.evaluate(
        _FIT_COVER_TITLE_JS,
        {"maxLines": max_lines, "minFontSize": min_font_size},
    )
    return result if isinstance(result, dict) else None
