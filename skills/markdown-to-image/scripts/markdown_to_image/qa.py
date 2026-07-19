"""Quality checks for markdown article slide generation."""

from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from markdown_to_image.browser import launch_browser
from markdown_to_image.render import render_article_slides
from markdown_to_image.layout import AVAILABLE_TEXT_HEIGHT, page_content_height
from markdown_to_image.overflow import (
    _BODY_OVERFLOW_JS,
    _UNDERFILL_SLACK_JS,
    _UNDERFILL_SLACK_RATIO,
)
from markdown_to_image.parser import (
    load_manifest,
    merge_manifest_defaults,
    parse_article_file,
    resolve_source_path,
    validate_required_manifest_fields,
)
from markdown_to_image.paginator import paginate_blocks
from markdown_to_image.config import enrich_manifest_from_article, load_renderer_config, normalize_platform

_VIEWPORT = {"width": 1080, "height": 1440}
_MIN_MID_PAGE_FILL = 0.72
_MIN_TAIL_PAGE_FILL = 0.45
_MIN_COVER_CONTRAST_RATIO = 3.0

_COVER_LAYOUT_JS = """
() => {
  const slide = document.querySelector('.slide-cover');
  const card = document.querySelector('.cover-title-card');
  const title = document.querySelector('.cover-title');
  if (!slide || !card || !title) return null;
  const slideRect = slide.getBoundingClientRect();
  const cardRect = card.getBoundingClientRect();
  const titleRect = title.getBoundingClientRect();
  const outside = (rect) => (
    rect.left < slideRect.left - 1 ||
    rect.top < slideRect.top - 1 ||
    rect.right > slideRect.right + 1 ||
    rect.bottom > slideRect.bottom + 1
  );
  return {
    overflow: outside(cardRect) || outside(titleRect),
    backgroundImage: Boolean(slide.style.backgroundImage),
    backgroundClass: slide.classList.contains('has-background-image'),
  };
}
"""

_COVER_CONTRAST_JS = r"""
async ({ backgroundDataUrl, blackDataUrl, whiteDataUrl, foregroundColor, foregroundOpacity }) => {
  const loadPixels = async (dataUrl) => {
    const image = new Image();
    image.src = dataUrl;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    context.drawImage(image, 0, 0);
    return {
      width: image.width,
      height: image.height,
      pixels: context.getImageData(0, 0, image.width, image.height).data,
    };
  };
  const [background, black, white] = await Promise.all([
    loadPixels(backgroundDataUrl),
    loadPixels(blackDataUrl),
    loadPixels(whiteDataUrl),
  ]);
  if (
    background.width !== black.width ||
    background.width !== white.width ||
    background.height !== black.height ||
    background.height !== white.height
  ) return null;

  const colorMatch = String(foregroundColor).match(
    /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)/i
  );
  if (!colorMatch) return null;
  const foreground = [
    Number(colorMatch[1]),
    Number(colorMatch[2]),
    Number(colorMatch[3]),
  ];
  const foregroundAlpha = Math.max(
    0,
    Math.min(1, Number(colorMatch[4] ?? 1) * Number(foregroundOpacity ?? 1))
  );
  const channel = (value) => {
    const normalized = value / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : Math.pow((normalized + 0.055) / 1.055, 2.4);
  };
  const luminance = (rgb) => (
    0.2126 * channel(rgb[0]) +
    0.7152 * channel(rgb[1]) +
    0.0722 * channel(rgb[2])
  );

  const ratios = [];
  for (let index = 0; index < background.pixels.length; index += 4) {
    const coverage = Math.max(
      Math.abs(white.pixels[index] - black.pixels[index]),
      Math.abs(white.pixels[index + 1] - black.pixels[index + 1]),
      Math.abs(white.pixels[index + 2] - black.pixels[index + 2])
    ) / 255;
    if (coverage < 0.5) continue;

    const backgroundRgb = [
      background.pixels[index],
      background.pixels[index + 1],
      background.pixels[index + 2],
    ];
    const renderedForeground = foreground.map(
      (value, channelIndex) => (
        value * foregroundAlpha + backgroundRgb[channelIndex] * (1 - foregroundAlpha)
      )
    );
    const backgroundLuminance = luminance(backgroundRgb);
    const foregroundLuminance = luminance(renderedForeground);
    const light = Math.max(backgroundLuminance, foregroundLuminance);
    const dark = Math.min(backgroundLuminance, foregroundLuminance);
    ratios.push((light + 0.05) / (dark + 0.05));
  }
  if (!ratios.length) return { ratio: 1, textPixels: 0 };

  ratios.sort((left, right) => left - right);
  const at = (percentile) => ratios[Math.min(
    ratios.length - 1,
    Math.floor((ratios.length - 1) * percentile)
  )];
  return {
    ratio: at(0.1),
    minimum: ratios[0],
    median: at(0.5),
    textPixels: ratios.length,
  };
}
"""


@dataclass(frozen=True)
class QAIssue:
    severity: Literal["error", "warning"]
    code: str
    message: str


def _cover_contrast_metrics(page, title) -> dict | None:
    rect = title.bounding_box()
    if not isinstance(rect, dict):
        return None

    viewport = page.viewport_size
    if not isinstance(viewport, dict):
        return None
    x = max(0.0, float(rect["x"]))
    y = max(0.0, float(rect["y"]))
    right = min(float(viewport["width"]), float(rect["x"]) + float(rect["width"]))
    bottom = min(float(viewport["height"]), float(rect["y"]) + float(rect["height"]))
    if right <= x or bottom <= y:
        return None
    clip = {"x": x, "y": y, "width": right - x, "height": bottom - y}

    computed_style = title.evaluate(
        """element => {
          const style = getComputedStyle(element);
          return { color: style.color, opacity: style.opacity };
        }"""
    )
    if not isinstance(computed_style, dict):
        return None
    original_style = title.get_attribute("style")

    def screenshot_data_url() -> str:
        screenshot = page.screenshot(type="png", clip=clip)
        return "data:image/png;base64," + base64.b64encode(screenshot).decode("ascii")

    page.evaluate("() => document.fonts.ready")
    try:
        title.evaluate("element => { element.style.visibility = 'hidden'; }")
        background_data_url = screenshot_data_url()
        mask_script = """(element, color) => {
          element.style.setProperty('visibility', 'visible', 'important');
          element.style.setProperty('color', color, 'important');
          element.style.setProperty('-webkit-text-fill-color', color, 'important');
          element.style.setProperty('text-shadow', 'none', 'important');
          element.style.setProperty('opacity', '1', 'important');
        }"""
        title.evaluate(mask_script, "#000")
        black_data_url = screenshot_data_url()
        title.evaluate(mask_script, "#fff")
        white_data_url = screenshot_data_url()
    finally:
        title.evaluate(
            """(element, styleValue) => {
              if (styleValue === null) element.removeAttribute('style');
              else element.setAttribute('style', styleValue);
            }""",
            original_style,
        )

    metrics = page.evaluate(
        _COVER_CONTRAST_JS,
        {
            "backgroundDataUrl": background_data_url,
            "blackDataUrl": black_data_url,
            "whiteDataUrl": white_data_url,
            "foregroundColor": computed_style.get("color"),
            "foregroundOpacity": computed_style.get("opacity"),
        },
    )
    return metrics if isinstance(metrics, dict) else None


def _project_root_from_manifest(manifest: dict) -> Path | None:
    raw = manifest.get("project_root")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw.strip()).expanduser().resolve()


def _pagination_issues(blocks: list, max_chars: int) -> list[QAIssue]:
    issues: list[QAIssue] = []
    text_segment: list = []
    slide_offset = 0

    def audit_text_segment(segment: list, offset: int) -> int:
        if not segment:
            return offset
        pages = paginate_blocks(segment, max_chars)
        for index, page in enumerate(pages):
            height = page_content_height(page)
            ratio = height / AVAILABLE_TEXT_HEIGHT if AVAILABLE_TEXT_HEIGHT else 0.0
            is_last = index == len(pages) - 1
            min_ratio = _MIN_TAIL_PAGE_FILL if is_last else _MIN_MID_PAGE_FILL
            if ratio < min_ratio:
                issues.append(
                    QAIssue(
                        "warning",
                        "sparse_page",
                        f"Estimated fill for body slide {offset + index + 1} is {ratio:.0%} "
                        f"(target ≥ {min_ratio:.0%}).",
                    )
                )
        return offset + len(pages)

    for block in blocks:
        if block.kind == "image":
            slide_offset = audit_text_segment(text_segment, slide_offset)
            text_segment = []
            slide_offset += 1
            continue
        text_segment.append(block)

    audit_text_segment(text_segment, slide_offset)
    return issues


def _link_issues(blocks: list) -> list[QAIssue]:
    issues: list[QAIssue] = []
    for block in blocks:
        text = block.text
        if "](http" in text or "](https" in text:
            issues.append(
                QAIssue(
                    "error",
                    "markdown_link",
                    "Body still contains markdown link syntax; anchor text only is expected.",
                )
            )
            break
        if '<a href="' in text:
            issues.append(
                QAIssue(
                    "error",
                    "html_link",
                    "Body still contains HTML anchor tags.",
                )
            )
            break
    return issues


def _render_issues(manifest_path: Path) -> list[QAIssue]:
    issues: list[QAIssue] = []
    try:
        slides, _ = render_article_slides(manifest_path)
    except Exception as exc:
        return [QAIssue("error", "render_failed", f"Render failed during QA: {exc}")]

    from playwright.sync_api import sync_playwright

    body_slides = [
        (name, html)
        for name, html in slides
        if name not in {"01-cover.png"} and not name.endswith("-end.png")
    ]
    cover_slides = [(name, html) for name, html in slides if name == "01-cover.png"]

    try:
        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(viewport=_VIEWPORT)
                for name, html in cover_slides:
                    page.set_content(html, wait_until="load")
                    title = page.locator(".cover-title")
                    kicker = page.locator(".cover-kicker")
                    if (
                        title.count() != 1
                        or kicker.count() != 1
                        or not title.inner_text().strip()
                        or not kicker.inner_text().strip()
                        or not title.is_visible()
                        or not kicker.is_visible()
                    ):
                        issues.append(
                            QAIssue(
                                "error",
                                "missing_cover_text",
                                f"{name}: cover title or category label is missing or hidden.",
                            )
                        )
                        continue
                    cover_metrics = page.evaluate(_COVER_LAYOUT_JS)
                    if not isinstance(cover_metrics, dict):
                        issues.append(
                            QAIssue(
                                "error",
                                "missing_cover_layout",
                                f"{name}: expected cover layout elements were not rendered.",
                            )
                        )
                        continue
                    if cover_metrics.get("overflow"):
                        issues.append(
                            QAIssue(
                                "error",
                                "cover_overflow",
                                f"{name}: cover title card exceeds the slide bounds.",
                            )
                        )
                    if cover_metrics.get("backgroundImage") != cover_metrics.get("backgroundClass"):
                        issues.append(
                            QAIssue(
                                "error",
                                "cover_background_state",
                                f"{name}: cover background style and state class disagree.",
                            )
                        )
                    contrast_metrics = _cover_contrast_metrics(page, title)
                    if not contrast_metrics:
                        issues.append(
                            QAIssue(
                                "error",
                                "cover_contrast_unavailable",
                                f"{name}: could not measure cover title contrast.",
                            )
                        )
                    else:
                        contrast_ratio = float(contrast_metrics.get("ratio") or 0)
                        if contrast_ratio < _MIN_COVER_CONTRAST_RATIO:
                            issues.append(
                                QAIssue(
                                    "error",
                                    "cover_low_contrast",
                                    f"{name}: cover title contrast is {contrast_ratio:.2f}:1 "
                                    f"(minimum {_MIN_COVER_CONTRAST_RATIO:.1f}:1).",
                                )
                            )
                for slide_index, (name, html) in enumerate(body_slides):
                    page.set_content(html, wait_until="load")
                    is_photo_slide = bool(page.locator(".article-photo-card").count())
                    has_text_body = bool(page.locator(".article-body-text").count())
                    if is_photo_slide and not has_text_body:
                        continue
                    if not has_text_body:
                        issues.append(
                            QAIssue(
                                "error",
                                "missing_body_text",
                                f"{name}: body slide has neither article text nor photo content.",
                            )
                        )
                        continue
                    if page.evaluate(_BODY_OVERFLOW_JS):
                        issues.append(
                            QAIssue(
                                "error",
                                "overflow",
                                f"{name}: text exceeds the slide body area.",
                            )
                        )
                    is_last_body = slide_index == len(body_slides) - 1
                    metrics = page.evaluate(_UNDERFILL_SLACK_JS)
                    if isinstance(metrics, dict) and not is_last_body:
                        client_height = float(metrics.get("clientHeight") or 0)
                        slack = float(metrics.get("slack") or 0)
                        if client_height > 0 and slack / client_height >= _UNDERFILL_SLACK_RATIO:
                            issues.append(
                                QAIssue(
                                    "warning",
                                    "underfill",
                                    f"{name}: large empty area below text "
                                    f"({slack / client_height:.0%} slack).",
                                )
                            )
                page.close()
            finally:
                browser.close()
    except Exception as exc:
        issues.append(
            QAIssue(
                "warning",
                "playwright_unavailable",
                f"Skipped render QA (Playwright): {exc}",
            )
        )
    return issues


def audit_article_manifest(
    manifest_path: Path,
    *,
    include_render: bool = True,
) -> list[QAIssue]:
    manifest_path = manifest_path.resolve()
    raw_manifest = load_manifest(manifest_path)
    project_root = _project_root_from_manifest(raw_manifest)
    config = load_renderer_config(manifest_path.parent, project_root)
    manifest = merge_manifest_defaults(raw_manifest, config)
    platform = normalize_platform(manifest.get("platform"))
    project_root = _project_root_from_manifest(manifest)
    validate_required_manifest_fields(manifest)
    source_path = resolve_source_path(manifest, manifest_path)
    article = parse_article_file(source_path)
    manifest = enrich_manifest_from_article(manifest, article.metadata, config, project_root)
    max_chars = int(manifest.get("chars_per_slide", 340))

    issues: list[QAIssue] = []
    issues.extend(_link_issues(article.blocks))
    if not include_render and platform != "x":
        issues.extend(_pagination_issues(article.blocks, max_chars))
    if include_render:
        issues.extend(_render_issues(manifest_path))
    return issues


def format_issues(issues: list[QAIssue]) -> str:
    if not issues:
        return "QA passed: no issues found."
    lines = []
    for issue in issues:
        lines.append(f"[{issue.severity}] {issue.code}: {issue.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run markdown article slide QA checks.")
    parser.add_argument("--manifest", required=True, type=Path, help="Path to manifest.json")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print issues as JSON (for automation).",
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Skip Playwright render checks.",
    )
    args = parser.parse_args(argv)

    issues = audit_article_manifest(
        args.manifest,
        include_render=not args.estimate_only,
    )
    if args.json:
        payload = [{"severity": i.severity, "code": i.code, "message": i.message} for i in issues]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_issues(issues))

    if any(issue.severity == "error" for issue in issues):
        return 1
    if any(issue.severity == "warning" for issue in issues):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
