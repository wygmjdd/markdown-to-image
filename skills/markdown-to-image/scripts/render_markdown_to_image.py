#!/usr/bin/env python3
"""Render markdown article slides to PNG images."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from markdown_to_image.browser import launch_browser
from markdown_to_image.qa import audit_article_manifest, format_issues
from markdown_to_image.render import COVER_BASE_FILENAME, render_article_slides

_VIEWPORT = {"width": 1080, "height": 1440}
_GENERATED_SLIDE_IMAGE_RE = re.compile(r"^(?:01-cover|0[2-9]|[1-9]\d|(?:0[2-9]|[1-9]\d)-end)\.png$")


def screenshot_slides(slides: list[tuple[str, str]], output_dir: Path) -> list[Path]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: playwright package not installed. Run:\n"
            "  python -m pip install -r requirements.txt",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from None

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as playwright:
        try:
            browser = launch_browser(playwright)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
            raise SystemExit(1) from exc
        try:
            page = browser.new_page(viewport=_VIEWPORT, device_scale_factor=2)
            page.set_default_timeout(60_000)
            for filename, slide_html in slides:
                out_path = output_dir / filename
                page.set_content(slide_html, wait_until="load")
                page.screenshot(path=str(out_path), full_page=False, timeout=60_000)
                written.append(out_path)
        finally:
            browser.close()

    return written


def prune_stale_slide_images(output_dir: Path, keep: set[str]) -> None:
    preserve = keep | {COVER_BASE_FILENAME}
    for path in output_dir.glob("*.png"):
        if path.name not in preserve:
            if _GENERATED_SLIDE_IMAGE_RE.match(path.name):
                path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render markdown article slides to PNG images.")
    parser.add_argument("--manifest", required=True, type=Path, help="Path to manifest.json")
    parser.add_argument("--qa", action="store_true", help="Run QA checks after rendering")
    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    slides, output_dir = render_article_slides(manifest_path)
    paths = screenshot_slides(slides, output_dir)
    prune_stale_slide_images(output_dir, {path.name for path in paths})

    print(f"Generated {len(paths)} images in {output_dir}")
    for path in paths:
        print(f"  {path.name}")

    if args.qa:
        issues = audit_article_manifest(manifest_path, include_render=True)
        print(format_issues(issues), flush=True)
        if any(issue.severity == "error" for issue in issues):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
