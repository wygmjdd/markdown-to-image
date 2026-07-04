"""Shared Playwright browser launch helpers."""

from __future__ import annotations

from typing import Any


PLAYWRIGHT_INSTALL_HINT = (
    "Playwright Chromium is not installed and system Chrome fallback did not launch. "
    "Run:\n"
    "  python -m pip install -r requirements.txt\n"
    "  python -m playwright install chromium"
)


def launch_browser(playwright: Any) -> Any:
    """Launch Playwright Chromium, falling back to the user's system Chrome."""
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as first_error:
        try:
            return playwright.chromium.launch(headless=True, channel="chrome")
        except Exception as second_error:
            message = f"{first_error}\n{second_error}"
            if "Executable doesn't exist" in message or "playwright install" in message.lower():
                raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from second_error
            raise second_error from first_error
