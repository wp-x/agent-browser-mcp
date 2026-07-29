from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

from .browsers import normalize_browser
from .tmwebdriver import TMWebDriver

ROOT = Path(__file__).resolve().parent
_DRIVER_PORT = int(os.environ.get("AGENT_BROWSER_TMWD_PORT", "18765"))
_DRIVER_HOST = os.environ.get("AGENT_BROWSER_TMWD_HOST", "127.0.0.1")
_driver: TMWebDriver | None = None


def chrome_extension_dir() -> Path:
    return ROOT / "chrome_extension"


def ensure_config_js() -> Path:
    path = chrome_extension_dir() / "config.js"
    if not path.exists():
        token = hex(random.randint(0, 99999999))[2:8]
        path.write_text(f"const TID = '__ljq_{token}';", encoding="utf-8")
    return path


def get_driver() -> TMWebDriver:
    global _driver
    ensure_config_js()
    if _driver is None:
        _driver = TMWebDriver(host=_DRIVER_HOST, port=_DRIVER_PORT)
    return _driver


def active_sessions(browser: str | None = None) -> list[dict[str, Any]]:
    return get_driver().get_all_sessions(normalize_browser(browser))


def ensure_sessions(browser: str | None = None) -> list[dict[str, Any]]:
    browser = normalize_browser(browser)
    sessions = active_sessions(browser)
    if not sessions:
        raise RuntimeError(
            f"No connected tabs for {browser}. Load the extension in that browser, "
            "select its browser identity in the popup, and open a normal http/https page."
        )
    return sessions


def switch_session(
    session_id: str | None = None,
    url_pattern: str | None = None,
    browser: str | None = None,
) -> str:
    driver = get_driver()
    browser = normalize_browser(browser)
    if session_id is not None:
        sid = driver.resolve_session_id(session_id, browser)
        if not any(str(item["id"]) == sid for item in active_sessions(browser)):
            raise RuntimeError(f"Session {sid} not found")
        driver.default_session_ids[browser] = sid
        return sid
    if url_pattern:
        sid = driver.set_session(url_pattern, browser)
        if not sid:
            raise RuntimeError(f"No {browser} session matching URL pattern: {url_pattern}")
        return str(sid)
    if driver.default_session_ids.get(browser):
        return driver.default_session_ids[browser]
    sessions = ensure_sessions(browser)
    driver.default_session_ids[browser] = str(sessions[0]["id"])
    return driver.default_session_ids[browser]


def exec_js(
    script: str,
    session_id: str | None = None,
    *,
    timeout: float = 15.0,
    browser: str | None = None,
) -> dict[str, Any]:
    driver = get_driver()
    if session_id is not None:
        switch_session(session_id=session_id, browser=browser)
    return driver.execute_js(script, timeout=timeout, browser=browser)


def compact_tabs(browser: str | None = None, *, all_browsers: bool = False):
    sessions = get_driver().get_all_sessions() if all_browsers else active_sessions(browser)
    tabs = []
    for session in sessions:
        item = dict(session)
        item.pop("connected_at", None)
        item.pop("type", None)
        tabs.append(item)
    return tabs


def bridge_status() -> dict[str, Any]:
    return {
        "tmwebdriver_host": _DRIVER_HOST,
        "tmwebdriver_ws_port": _DRIVER_PORT,
        "tmwebdriver_http_port": _DRIVER_PORT + 1,
    }
