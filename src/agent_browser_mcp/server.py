from __future__ import annotations

import json
import os
from typing import Any, Optional

os.environ.setdefault("PYAUTO_GUI_NO_FAILSAFE", "1")

from mcp.server.fastmcp import FastMCP

from .browsers import DEFAULT_BROWSER, SUPPORTED_BROWSERS, normalize_browser  # noqa: E402
from .desktop_tools import register_desktop_tools  # noqa: E402
from .page_tools import register_page_tools  # noqa: E402
from .runtime import (  # noqa: E402
    ROOT,
    bridge_status,
    chrome_extension_dir,
    compact_tabs,
    ensure_config_js,
    exec_js,
    get_driver,
    switch_session,
)

mcp = FastMCP(
    name="agent-browser",
    instructions=(
        "Browser automation tools for the user's real Chrome session via TMWebDriver/CDP bridge. "
        "Supports page scanning, JS execution, CDP commands, screenshots, cookies, and desktop physical input."
    ),
)

@mcp.tool(description="Return extension path, bridge ports, and connection status for setup/diagnostics.")
def get_setup_status() -> dict[str, Any]:
    driver = get_driver()
    sessions = compact_tabs(all_browsers=True)
    return {
        "extension_name": "TMWD CDP Bridge",
        "extension_path": str(chrome_extension_dir()),
        "config_js": str(ensure_config_js()),
        **bridge_status(),
        "remote_mode": driver.is_remote,
        "connected_tabs": len(sessions),
        "supported_browsers": list(SUPPORTED_BROWSERS),
        "default_browser": DEFAULT_BROWSER,
        "default_session_ids": driver.default_session_ids,
        "tabs": sessions,
        "notes": [
            "Load the extension in each browser and select its identity from the popup.",
            "Keep a normal http/https page open in Chrome; about:blank is not enough.",
            "This MCP server hosts TMWebDriver itself unless another compatible bridge is already listening.",
        ],
    }


@mcp.tool(description="List tabs. Defaults to Google Chrome; pass browser='Google Chrome Dev' for Dev.")
def list_tabs(browser: str | None = None) -> dict[str, Any]:
    browser = normalize_browser(browser)
    sessions = compact_tabs(browser)
    return {
        "browser": browser,
        "default_session_id": get_driver().default_session_ids.get(browser),
        "tabs": sessions,
    }


@mcp.tool(description="Set the active tab in Google Chrome or Google Chrome Dev.")
def switch_tab(
    session_id: Optional[str] = None,
    url_pattern: Optional[str] = None,
    browser: str | None = None,
) -> dict[str, Any]:
    browser = normalize_browser(browser)
    sid = switch_session(session_id, url_pattern, browser)
    return {"browser": browser, "active_session_id": sid, "tabs": compact_tabs(browser)}


@mcp.tool(description="Navigate the current tab to a URL using real-browser JS navigation.")
def open_url(
    url: str,
    session_id: Optional[str] = None,
    *,
    timeout: float = 15.0,
    browser: str | None = None,
) -> dict[str, Any]:
    browser = normalize_browser(browser)
    if session_id is not None:
        switch_session(session_id=session_id, browser=browser)
    driver = get_driver()
    driver.jump(url, timeout=timeout, browser=browser)
    return {
        "status": "ok",
        "browser": browser,
        "active_session_id": driver.default_session_ids.get(browser),
        "url": url,
    }


@mcp.tool(description="Open a new browser tab with the given URL.")
def open_new_tab(url: str, browser: str | None = None) -> dict[str, Any]:
    browser = normalize_browser(browser)
    driver = get_driver()
    result = driver.newtab(url, browser=browser)
    return {"status": "ok", "browser": browser, "result": result, "tabs": compact_tabs(browser)}


@mcp.tool(description="Get absolute path to the unpacked Chrome extension directory for manual installation.")
def extension_path(browser: str | None = None) -> dict[str, Any]:
    return {
        "browser": normalize_browser(browser),
        "extension_path": str(chrome_extension_dir()),
        "config_js": str(ensure_config_js()),
        "setup": "Load this path, then select the browser identity in the extension popup.",
    }


@mcp.tool(description="List Chrome extensions visible to the CDP bridge extension itself.")
def list_extensions(
    session_id: Optional[str] = None,
    browser: str | None = None,
) -> dict[str, Any]:
    if session_id is not None:
        switch_session(session_id=session_id, browser=browser)
    return exec_js(
        json.dumps({"cmd": "management", "method": "list"}),
        timeout=20.0,
        browser=browser,
    )


register_page_tools(mcp)
register_desktop_tools(mcp, ROOT)


if __name__ == "__main__":
    ensure_config_js()
    get_driver()
    mcp.run(transport="stdio")
