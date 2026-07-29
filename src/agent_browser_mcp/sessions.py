from __future__ import annotations

import time
from typing import Any

from .logging_utils import log


class Session:
    def __init__(self, session_id: str, info: dict[str, Any], client: Any = None):
        self.id = session_id
        self.info = info
        self.connect_at = time.time()
        self.disconnect_at: float | None = None
        self.type = info.get("type", "ws")
        self.ws_client = client if self.type in ("ws", "ext_ws") else None
        self.http_queue = client if self.type == "http" else None

    @property
    def url(self) -> str:
        return self.info.get("url", "")

    @property
    def browser(self) -> str:
        return self.info["browser"]

    @property
    def tab_id(self) -> str:
        return str(self.info["tab_id"])

    def is_active(self) -> bool:
        if self.type == "http" and time.time() - self.connect_at > 60:
            self.mark_disconnected()
        return self.disconnect_at is None

    def reconnect(self, client: Any, info: dict[str, Any]) -> None:
        self.info = info
        self.type = info.get("type", "ws")
        if self.type in ("ws", "ext_ws"):
            self.ws_client = client
            self.http_queue = None
        elif self.type == "http":
            self.http_queue = client
        self.connect_at = time.time()
        self.disconnect_at = None

    def mark_disconnected(self) -> None:
        if self.disconnect_at is None:
            log(f"Tab disconnected: {self.url} (Session: {self.id})")
        self.disconnect_at = time.time()
