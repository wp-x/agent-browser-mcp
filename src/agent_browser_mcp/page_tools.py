from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from . import simphtml
from .browser_driver import BrowserDriver
from .browsers import normalize_browser
from .runtime import compact_tabs, ensure_sessions, exec_js, get_driver, switch_session


def register_page_tools(mcp: Any) -> None:
    mcp.tool(description="Read the current page as simplified HTML/text.") (scan_page)
    mcp.tool(description="Execute JavaScript in the selected real Chrome browser.") (execute_js)
    mcp.tool(description="Call one Chrome DevTools Protocol command.") (cdp_command)
    mcp.tool(description="Run a CDP bridge batch command.") (cdp_batch)
    mcp.tool(description="Get cookies for the selected browser tab.") (get_cookies)
    mcp.tool(description="Capture a screenshot of the selected browser tab.") (capture_page_screenshot)


def scan_page(
    session_id: str | None = None,
    *,
    browser: str | None = None,
    text_only: bool = False,
    cutlist: bool = True,
    maxchars: int = 35000,
    instruction: str = "",
    extra_js: str = "",
) -> dict[str, Any]:
    driver, browser = _selected_driver(session_id, browser)
    content = simphtml.get_html(
        driver,
        cutlist=cutlist,
        maxchars=maxchars,
        instruction=instruction,
        extra_js=extra_js,
        text_only=text_only,
    )
    return _page_result(browser, content)


def execute_js(
    script: str,
    session_id: str | None = None,
    *,
    browser: str | None = None,
    no_monitor: bool = False,
) -> dict[str, Any]:
    driver, _ = _selected_driver(session_id, browser)
    return simphtml.execute_js_rich(script, driver, no_monitor=no_monitor)


def cdp_command(
    method: str,
    params_json: str = "{}",
    *,
    session_id: str | None = None,
    tab_id: int | None = None,
    browser: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "cmd": "cdp",
        "method": method,
        "params": json.loads(params_json or "{}"),
    }
    if tab_id is not None:
        payload["tabId"] = tab_id
    return _bridge_command(payload, session_id, browser, 20.0)


def cdp_batch(
    batch_json: str,
    session_id: str | None = None,
    browser: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(batch_json)
    if payload.get("cmd") != "batch":
        raise RuntimeError("batch_json must be a JSON object with cmd='batch'")
    return _bridge_command(payload, session_id, browser, 30.0)


def get_cookies(
    session_id: str | None = None,
    tab_id: int | None = None,
    browser: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"cmd": "cookies"}
    if tab_id is not None:
        payload["tabId"] = tab_id
    return _bridge_command(payload, session_id, browser, 15.0)


def capture_page_screenshot(
    session_id: str | None = None,
    tab_id: int | None = None,
    *,
    browser: str | None = None,
    format: str = "png",
    save_path: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "cmd": "cdp",
        "method": "Page.captureScreenshot",
        "params": {"format": format},
    }
    if tab_id is not None:
        payload["tabId"] = tab_id
    result = _bridge_command(payload, session_id, browser, 20.0)
    encoded = _screenshot_data(result)
    output = {"format": format, "base64": encoded}
    if save_path:
        path = Path(save_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(encoded))
        output["saved_to"] = str(path)
    return output


def _selected_driver(session_id, browser):
    browser = normalize_browser(browser)
    if session_id is not None:
        switch_session(session_id=session_id, browser=browser)
    ensure_sessions(browser)
    return BrowserDriver(get_driver(), browser), browser


def _bridge_command(payload, session_id, browser, timeout):
    if session_id is not None:
        switch_session(session_id=session_id, browser=browser)
    return exec_js(json.dumps(payload), timeout=timeout, browser=browser)


def _page_result(browser, content):
    driver = get_driver()
    return {
        "status": "success",
        "browser": browser,
        "active_session_id": driver.default_session_ids.get(browser),
        "tabs": compact_tabs(browser),
        "content": content,
    }


def _screenshot_data(result):
    data = result.get("data")
    return data["data"] if isinstance(data, dict) and "data" in data else data
