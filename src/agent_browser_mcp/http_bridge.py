from __future__ import annotations

import json
import queue
import threading
import time
import traceback
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import bottle
from bottle import request

from .browsers import normalize_browser, session_key
from .logging_utils import log
from .sessions import Session


def start_http_server(driver) -> None:
    app = bottle.Bottle()
    driver.app = app
    _register_long_poll(app, driver)
    _register_result(app, driver)
    _register_link(app, driver)
    thread = threading.Thread(target=_serve, args=(driver, app), daemon=True)
    thread.start()


def _register_long_poll(app, driver) -> None:
    @app.route("/api/longpoll", method=["GET", "POST"])
    def long_poll():
        data = request.json
        browser = normalize_browser(data.get("browser"))
        tab_id = str(data.get("sessionId"))
        sid = session_key(browser, tab_id)
        info = {
            "url": data.get("url"),
            "title": data.get("title", ""),
            "type": "http",
            "browser": browser,
            "tab_id": tab_id,
        }
        session = _http_session(driver, sid, info)
        if session.type != "http":
            return json.dumps({"id": "", "ret": "use ws"})
        return _poll_message(driver, session)


def _http_session(driver, sid, info):
    if sid not in driver.sessions:
        driver.sessions[sid] = Session(sid, info, queue.Queue())
        log(f"Browser http connected: {info['url']} (Session: {sid})")
    session = driver.sessions[sid]
    if session.disconnect_at is not None and session.type != "http":
        session.reconnect(queue.Queue(), info)
    session.disconnect_at = None
    return session


def _poll_message(driver, session):
    session.connect_at = started = time.time()
    while time.time() - started < 5:
        try:
            message = session.http_queue.get(timeout=0.2)
            try:
                driver.acks[json.loads(message).get("id", "")] = True
            except json.JSONDecodeError:
                traceback.print_exc()
            return message
        except queue.Empty:
            continue
    return json.dumps({"id": "", "ret": "next long-poll"})


def _register_result(app, driver) -> None:
    @app.route("/api/result", method=["GET", "POST"])
    def result():
        data = request.json
        success = data.get("type") == "result"
        driver.results[data.get("id")] = {
            "success": success,
            "data": data.get("result") if success else data.get("error"),
            "newTabs": data.get("newTabs", []),
        }
        return "ok"


def _register_link(app, driver) -> None:
    @app.route("/link", method=["GET", "POST"])
    def link():
        data = request.json
        command = data.get("cmd")
        browser = data.get("browser")
        if command == "get_all_sessions":
            result = driver.get_all_sessions(browser)
        elif command == "find_session":
            result = driver.find_session(data.get("url_pattern", ""), browser)
        elif command == "execute_js":
            result = _remote_execute(driver, data, browser)
        else:
            return "ok"
        return json.dumps({"r": result}, ensure_ascii=False)


def _remote_execute(driver, data, browser):
    try:
        return driver.execute_js(
            data.get("code"),
            timeout=float(data.get("timeout", 10.0)),
            session_id=data.get("sessionId"),
            browser=browser,
        )
    except Exception as error:
        return {"error": str(error)}


class _ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _QuietHandler(WSGIRequestHandler):
    def log_request(self, *args) -> None:
        return None


def _serve(driver, app) -> None:
    server = make_server(
        driver.host,
        driver.port + 1,
        app,
        server_class=_ThreadedServer,
        handler_class=_QuietHandler,
    )
    server.serve_forever()
