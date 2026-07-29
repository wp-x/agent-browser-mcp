import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_browser_mcp.browsers import (  # noqa: E402
    CHROME_DEV,
    DEFAULT_BROWSER,
    normalize_browser,
    session_key,
)
from agent_browser_mcp.tmwebdriver import TMWebDriver  # noqa: E402


class FakeClient:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(json.loads(message))


def make_driver():
    driver = TMWebDriver.__new__(TMWebDriver)
    driver.sessions = {}
    driver.results = {}
    driver.acks = {}
    driver.default_session_ids = {}
    driver.latest_session_ids = {}
    driver.is_remote = False
    return driver


def test_aliases():
    assert normalize_browser() == DEFAULT_BROWSER
    assert normalize_browser("chrome") == DEFAULT_BROWSER
    assert normalize_browser("开发浏览器") == CHROME_DEV
    assert normalize_browser("Google Chrome Dev") == CHROME_DEV


def test_same_tab_id_isolated_by_browser():
    driver = make_driver()
    stable_client = FakeClient()
    dev_client = FakeClient()
    tabs = [{"id": 7, "url": "https://example.com", "title": "Example"}]

    driver._register_tabs(tabs, DEFAULT_BROWSER, stable_client)
    driver._register_tabs(tabs, CHROME_DEV, dev_client)

    assert set(driver.sessions) == {
        session_key(DEFAULT_BROWSER, 7),
        session_key(CHROME_DEV, 7),
    }
    assert len(driver.get_all_sessions(DEFAULT_BROWSER)) == 1
    assert len(driver.get_all_sessions(CHROME_DEV)) == 1
    assert driver.resolve_session_id("7", CHROME_DEV) == session_key(CHROME_DEV, 7)


def test_command_routes_to_selected_browser():
    driver = make_driver()
    stable_client = FakeClient()
    dev_client = FakeClient()
    driver._register_tabs([{"id": 11}], DEFAULT_BROWSER, stable_client)
    driver._register_tabs([{"id": 11}], CHROME_DEV, dev_client)

    dev_session = driver.sessions[session_key(CHROME_DEV, 11)]
    driver._send_command(dev_session, "document.title")

    assert stable_client.messages == []
    assert dev_client.messages[0]["tabId"] == 11


def test_extension_declares_identity_support():
    extension = ROOT / "src" / "agent_browser_mcp" / "chrome_extension"
    manifest = json.loads((extension / "manifest.json").read_text())
    background = (extension / "background.js").read_text()

    assert "storage" in manifest["permissions"]
    assert "Google Chrome Dev" in background
    assert "browser: browserName" in background


if __name__ == "__main__":
    tests = [
        test_aliases,
        test_same_tab_id_isolated_by_browser,
        test_command_routes_to_selected_browser,
        test_extension_declares_identity_support,
    ]
    for test in tests:
        test()
    print("BROWSER_ROUTING_OK")
