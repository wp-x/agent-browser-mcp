from __future__ import annotations

from .browsers import normalize_browser


class BrowserDriver:
    def __init__(self, driver, browser: str | None = None):
        self.driver = driver
        self.browser = normalize_browser(browser)

    @property
    def default_session_id(self):
        return self.driver.default_session_ids.get(self.browser)

    @default_session_id.setter
    def default_session_id(self, session_id):
        self.driver.default_session_ids[self.browser] = str(session_id)

    def execute_js(self, code, timeout=15, session_id=None):
        return self.driver.execute_js(
            code,
            timeout=timeout,
            session_id=session_id,
            browser=self.browser,
        )

    def get_session_dict(self):
        sessions = self.driver.get_all_sessions(self.browser)
        return {session["id"]: session["url"] for session in sessions}
