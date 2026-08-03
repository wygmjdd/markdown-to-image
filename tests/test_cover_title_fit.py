from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from markdown_to_image.browser import fit_cover_title, launch_browser
from markdown_to_image import qa
from markdown_to_image.render import _render_cover_slide, clear_css_cache


def _fit_title(title: str) -> dict:
    clear_css_cache()
    html = _render_cover_slide(
        {"social_title": title, "cta_theme": "reading"},
        ROOT,
    )
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1440})
            page.set_content(html, wait_until="load")
            metrics = fit_cover_title(page)
        finally:
            browser.close()
    assert metrics is not None
    return metrics


def test_medium_cover_title_fits_on_two_lines() -> None:
    metrics = _fit_title("为什么我读世界名著，总能遇见拿破仑？")

    assert metrics["initialFontSize"] == 96
    assert metrics["fontSize"] == 93
    assert metrics["lines"] == ["为什么我读世界名著，", "总能遇见拿破仑？"]


def test_cover_title_fit_handles_different_punctuation_positions() -> None:
    metrics = _fit_title("一二三四五六七八九十，甲乙丙丁戊己庚辛壬")

    assert metrics["initialFontSize"] == 96
    assert metrics["fontSize"] >= 74
    assert metrics["lineCount"] == 2
    assert metrics["lastLineLength"] > 3


def test_cover_qa_rejects_orphan_line_at_minimum_font_size(
    monkeypatch,
    tmp_path: Path,
) -> None:
    orphan_cover = """
    <!doctype html>
    <html>
      <head>
        <style>
          html, body { margin: 0; }
          .slide { width: 1080px; height: 1440px; background: #fff; }
          .cover-title-card { width: 740px; margin: 120px; }
          .cover-kicker { color: #222; font: 24px sans-serif; }
          .cover-title { width: 740px; color: #222; font: 74px/1.2 sans-serif; }
        </style>
      </head>
      <body>
        <div class="slide slide-cover">
          <div class="cover-title-card">
            <div class="cover-kicker">读书感悟</div>
            <div class="cover-title">一二三四五六七八九十甲乙丙丁戊己庚辛壬癸天地</div>
          </div>
        </div>
      </body>
    </html>
    """
    monkeypatch.setattr(
        qa,
        "render_article_slides",
        lambda _manifest_path: ([("01-cover.png", orphan_cover)], {}),
    )

    issues = qa._render_issues(tmp_path / "manifest.json")

    assert any(issue.code == "cover_title_orphan_line" for issue in issues)
