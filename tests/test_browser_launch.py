from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"


def _import_browser_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import browser

    return browser


class _FakeChromium:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def launch(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return "chromium-browser"


class _FakePlaywright:
    def __init__(self, error: Exception | None = None) -> None:
        self.chromium = _FakeChromium(error)


def test_launch_browser_uses_bundled_chromium() -> None:
    browser = _import_browser_module()
    playwright = _FakePlaywright()

    launched = browser.launch_browser(playwright)

    assert launched == "chromium-browser"
    assert playwright.chromium.calls == [{"headless": True}]


def test_launch_browser_never_falls_back_to_system_chrome() -> None:
    browser = _import_browser_module()
    original_error = RuntimeError("browser process exited unexpectedly")
    playwright = _FakePlaywright(original_error)

    try:
        browser.launch_browser(playwright)
    except RuntimeError as error:
        assert error is original_error
    else:
        raise AssertionError("expected Chromium launch failure")

    assert playwright.chromium.calls == [{"headless": True}]


def test_launch_browser_explains_missing_chromium() -> None:
    browser = _import_browser_module()
    playwright = _FakePlaywright(RuntimeError("Executable doesn't exist"))

    try:
        browser.launch_browser(playwright)
    except RuntimeError as error:
        assert "System Chrome is intentionally not used" in str(error)
        assert "playwright install chromium" in str(error)
    else:
        raise AssertionError("expected missing Chromium failure")

    assert playwright.chromium.calls == [{"headless": True}]
