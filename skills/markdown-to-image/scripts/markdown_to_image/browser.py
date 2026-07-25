"""Shared Playwright browser launch helpers."""

from __future__ import annotations

from typing import Any


PLAYWRIGHT_INSTALL_HINT = (
    "Playwright Chromium is not installed. System Chrome is intentionally not used. "
    "Run:\n"
    "  python -m pip install -r requirements.txt\n"
    "  python -m playwright install chromium"
)


def launch_browser(playwright: Any) -> Any:
    """Launch Playwright Chromium without touching the user's system Chrome."""
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as error:
        message = str(error)
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from error
        raise
