import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from wsgiref.util import setup_testing_defaults

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_browser_mcp import simphtml
from agent_browser_mcp.tmwebdriver import (
    Session,
    TMWebDriver,
    is_allowed_websocket_origin,
    validate_loopback_host,
    validate_navigation_url,
)


EXT = ROOT / "src" / "agent_browser_mcp" / "chrome_extension"


class SelectiveSyncTests(unittest.TestCase):
    def test_http_app_rejects_browser_origin(self):
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.host, driver.port = "127.0.0.1", 18765
        driver.sessions, driver.results, driver.acks = {}, {}, {}
        with mock.patch("threading.Thread.start"):
            driver.start_http_server()

        environ = {}
        setup_testing_defaults(environ)
        environ.update(
            REQUEST_METHOD="POST",
            PATH_INFO="/link",
            CONTENT_TYPE="application/json",
            CONTENT_LENGTH="2",
            HTTP_ORIGIN="https://attacker.example",
            wsgi_input=io.BytesIO(b"{}"),
        )
        status = []
        body = b"".join(driver.app(environ, lambda s, h, exc_info=None: status.append(s)))
        self.assertTrue(status[0].startswith("403"), body)

    def test_remote_timeout_is_30_seconds_and_clear(self):
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.remote = "http://127.0.0.1:18766/link"
        import requests
        with mock.patch("agent_browser_mcp.tmwebdriver.requests.post", side_effect=requests.exceptions.Timeout) as post:
            with self.assertRaisesRegex(TimeoutError, "30s.*standalone TMWebDriver"):
                driver._remote_cmd({"cmd": "get_all_sessions"})
        self.assertEqual(post.call_args.kwargs["timeout"], 30)

    def test_remote_connection_error_is_standalone_specific(self):
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.remote = "http://127.0.0.1:18766/link"
        import requests
        with mock.patch("agent_browser_mcp.tmwebdriver.requests.post", side_effect=requests.exceptions.ConnectionError):
            with self.assertRaisesRegex(ConnectionError, "standalone TMWebDriver bridge"):
                driver._remote_cmd({})

    def test_extension_reconnect_rebinds_and_old_close_does_not_disconnect(self):
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.sessions, driver.default_session_id = {}, None
        driver.latest_session_id = None
        old_socket, new_socket = object(), object()
        info = {"url": "https://example.test", "type": "ext_ws"}
        driver._register_client("7", old_socket, info)
        driver._register_client("7", new_socket, info)
        driver._unregister_client(old_socket)
        session = driver.sessions["7"]
        self.assertIs(session.ws_client, new_socket)
        self.assertTrue(session.is_active())

    def test_websocket_origin_policy(self):
        self.assertTrue(is_allowed_websocket_origin("chrome-extension://install-dependent-id"))
        self.assertTrue(is_allowed_websocket_origin(None))
        self.assertFalse(is_allowed_websocket_origin("https://attacker.example"))
        self.assertFalse(is_allowed_websocket_origin("http://localhost:3000"))

    def test_loopback_bind_host_validation(self):
        for host in ("localhost", "127.0.0.1", "::1"):
            validate_loopback_host(host)
        for host in ("0.0.0.0", "192.168.1.2"):
            with self.assertRaisesRegex(ValueError, "loopback"):
                validate_loopback_host(host)

    def test_remote_detection_still_uses_loopback_master(self):
        fake_probe = mock.Mock()
        with mock.patch("agent_browser_mcp.tmwebdriver.socket.create_connection", return_value=fake_probe) as connect:
            driver = TMWebDriver("127.0.0.1", 18765)
        connect.assert_called_once_with(("127.0.0.1", 18766), timeout=0.25)
        fake_probe.close.assert_called_once_with()
        self.assertTrue(driver.is_remote)
        self.assertEqual(driver.remote, "http://127.0.0.1:18766/link")

    def test_navigation_url_validation_and_safe_serialization(self):
        self.assertEqual(validate_navigation_url("https://example.test/a?q=1"), "https://example.test/a?q=1")
        for value in (
            "javascript:alert(1)", "file:///tmp/a", "//example.test/a",
            "https://user:pass@example.test/", "https://example.test/\nalert(1)",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_navigation_url(value)
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.execute_js = mock.Mock()
        url = 'https://example.test/\";alert(1);//'
        driver.jump(url)
        self.assertEqual(driver.execute_js.call_args.args[0], "window.location.href=" + json.dumps(url))

    def test_duplicate_disconnect_logs_once_and_keeps_first_timestamp(self):
        session = Session("7", {"url": "https://example.test", "type": "ws"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            session.mark_disconnected()
            first = session.disconnect_at
            session.mark_disconnected()
        self.assertEqual(first, session.disconnect_at)
        self.assertEqual(out.getvalue().count("Tab disconnected"), 1)

    def test_new_tab_delegates_to_tabs_create_and_returns_tab_payload(self):
        driver = TMWebDriver.__new__(TMWebDriver)
        driver.execute_js = mock.Mock(return_value={"data": {"id": 42, "url": "https://example.test", "title": "Example"}})
        result = driver.newtab("https://example.test")
        payload = json.loads(driver.execute_js.call_args.args[0])
        self.assertEqual(payload, {"cmd": "tabs", "method": "create", "url": "https://example.test"})
        self.assertEqual(result["data"]["id"], 42)

    def test_extension_static_invariants(self):
        manifest = json.loads((EXT / "manifest.json").read_text())
        background = (EXT / "background.js").read_text()
        content = (EXT / "content.js").read_text()
        all_sources = background + content
        self.assertEqual(manifest["content_scripts"][1]["js"], ["content.js"])
        self.assertIn("declarativeNetRequest", manifest["permissions"])
        self.assertIn("removeRuleIds: [9999]", background)
        self.assertNotIn("addRules", background)
        self.assertNotIn("Content-Security-Policy", content)
        self.assertIn('validateNavigationUrl(msg.url)', background)
        self.assertNotIn("chrome.management.setEnabled", background)
        self.assertNotIn("chrome.runtime.reload", background)
        self.assertIn("chrome.management.getAll", background)
        self.assertNotIn("contentSettings", manifest["permissions"])
        self.assertNotIn("navigator.webdriver", all_sources)
        self.assertIn("msg.method === 'create'", background)
        self.assertIn("tmwd_status", background)
        self.assertIn("id='ljq-ind'", content)
        self.assertNotIn("MutationObserver", content)
        self.assertFalse((EXT / "config.js").exists())

    def test_simphtml_flow_geometry_and_node_info_preserved(self):
        source = simphtml.js_optHTML
        self.assertIn("const flowChildren", source)
        self.assertIn("position !== 'fixed'", source)
        self.assertIn("position !== 'absolute'", source)
        self.assertIn("nodeInfo.set(clone, info);", source)
        self.assertIn("const ignoreIds = ['ljq-ind'];", source)


if __name__ == "__main__":
    unittest.main()
