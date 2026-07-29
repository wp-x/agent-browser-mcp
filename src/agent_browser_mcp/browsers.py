from __future__ import annotations

DEFAULT_BROWSER = "Google Chrome"
CHROME_DEV = "Google Chrome Dev"
SUPPORTED_BROWSERS = (DEFAULT_BROWSER, CHROME_DEV)

_ALIASES = {
    "chrome": DEFAULT_BROWSER,
    "google chrome": DEFAULT_BROWSER,
    "stable": DEFAULT_BROWSER,
    "稳定版": DEFAULT_BROWSER,
    "chrome dev": CHROME_DEV,
    "google chrome dev": CHROME_DEV,
    "dev": CHROME_DEV,
    "开发版": CHROME_DEV,
    "开发浏览器": CHROME_DEV,
}


def normalize_browser(browser: str | None = None) -> str:
    if browser is None or not browser.strip():
        return DEFAULT_BROWSER
    normalized = _ALIASES.get(browser.strip().lower())
    if normalized is None:
        supported = ", ".join(SUPPORTED_BROWSERS)
        raise ValueError(f"Unsupported browser '{browser}'. Supported browsers: {supported}")
    return normalized


def session_key(browser: str, tab_id: str | int) -> str:
    return f"{normalize_browser(browser)}::{tab_id}"
