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
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def launch(self, **kwargs):
        self.calls.append(kwargs)
        if "channel" not in kwargs:
            raise RuntimeError("Executable doesn't exist")
        return "chrome-browser"


class _FakePlaywright:
    def __init__(self) -> None:
        self.chromium = _FakeChromium()


def test_launch_browser_falls_back_to_system_chrome() -> None:
    browser = _import_browser_module()
    playwright = _FakePlaywright()

    launched = browser.launch_browser(playwright)

    assert launched == "chrome-browser"
    assert playwright.chromium.calls == [
        {"headless": True},
        {"headless": True, "channel": "chrome"},
    ]
