import json
import socket
import threading
import time
import uuid
import requests
from simple_websocket_server import WebSocket, WebSocketServer
from .browsers import normalize_browser, session_key
from .http_bridge import start_http_server
from .logging_utils import log
from .sessions import Session
class TMWebDriver:  
    def __init__(self, host: str = '127.0.0.1', port: int = 18765):  
        self.host, self.port = host, port
        self.sessions, self.results, self.acks = {}, {}, {}
        self.default_session_ids = {}
        self.latest_session_ids = {}
        self.is_remote = socket.socket().connect_ex((host, port+1)) == 0
        if not self.is_remote:  
            self.start_ws_server()  
            self.start_http_server()
        else:
            self.remote = f'http://{self.host}:{self.port+1}/link'

    def start_http_server(self):
        start_http_server(self)

    def clean_sessions(self):
        sids = list(self.sessions.keys())
        for sid in sids:
            session = self.sessions[sid]
            if not session.is_active() and time.time() - session.disconnect_at > 600:
                del self.sessions[sid]
    
    def start_ws_server(self) -> None:  
        driver = self  
        class JSExecutor(WebSocket):  
            def handle(self) -> None:  
                try:  
                    data = json.loads(self.data)  
                    if data.get('type') == 'ready':  
                        browser = normalize_browser(data.get('browser'))
                        tab_id = str(data.get('sessionId'))
                        info = driver._session_info(data, browser, tab_id, 'ws')
                        driver._register_client(session_key(browser, tab_id), self, info)
                    elif data.get('type') in ['ext_ready', 'tabs_update']:
                        browser = normalize_browser(data.get('browser'))
                        driver._register_tabs(data.get('tabs', []), browser, self)
                    elif data.get('type') == 'ack': driver.acks[data.get('id','')] = True
                    elif data.get('type') == 'result':  
                        driver.results[data.get('id')] = {'success': True, 'data': data.get('result'), 'newTabs': data.get('newTabs', [])}  
                    elif data.get('type') == 'error':  
                        driver.results[data.get('id')] = {'success': False, 'data': data.get('error'), 'newTabs': data.get('newTabs', [])}  
                except Exception as e:  
                    log(f"Error handling message: {e}")
                    if hasattr(self, 'data'): log(self.data)
            def connected(self): (f"New connection from {self.address}")  
            def handle_close(self): 
                log(f"WS Connection closed: {self.address}")
                driver._unregister_client(self)  
        
        self.server = WebSocketServer(self.host, self.port, JSExecutor)  
        server_thread = threading.Thread(target=self.server.serve_forever)  
        server_thread.daemon = True  
        server_thread.start()  
        log(f"WebSocket server running on ws://{self.host}:{self.port}")

    @staticmethod
    def _session_info(data, browser, tab_id, session_type):
        return {
            'url': data.get('url'),
            'title': data.get('title', ''),
            'connected_at': time.time(),
            'type': session_type,
            'browser': browser,
            'tab_id': tab_id,
        }

    def _register_tabs(self, tabs, browser, client):
        current_ids = {session_key(browser, tab['id']) for tab in tabs}
        log(f"Received {browser} tabs update: {current_ids}")
        for sid, session in self.sessions.items():
            if session.type == 'ext_ws' and session.ws_client == client and sid not in current_ids:
                session.mark_disconnected()
        for tab in tabs:
            tab_id = str(tab['id'])
            sid = session_key(browser, tab_id)
            info = self._session_info(tab, browser, tab_id, 'ext_ws')
            session = self.sessions.get(sid)
            if session and session.is_active():
                session.reconnect(client, info)
            else:
                self._register_client(sid, client, info)
    
    def _register_client(self, session_id: str, client: WebSocket, session_info) -> None:  
        is_new_session = session_id not in self.sessions

        if is_new_session:
            session = Session(session_id, session_info, client)
            self.sessions[session_id] = session            
            log(f"New tab connected: {session.url} (Session: {session_id})")
        else:
            session = self.sessions[session_id]
            session.reconnect(client, session_info)
            log(f"Tab reconnected: {session.url} (Session: {session_id})")

        browser = session_info['browser']
        self.latest_session_ids[browser] = session_id
        self.default_session_ids.setdefault(browser, session_id)
    
    def _unregister_client(self, client: WebSocket) -> None:  
        for session in self.sessions.values():
            if session.ws_client == client: session.mark_disconnected()
    
    def execute_js(self, code, timeout=15, session_id=None, browser=None):
        browser = normalize_browser(browser)
        session_id = self.resolve_session_id(session_id, browser)
        if self.is_remote:
            response = self._remote_execute(code, timeout, session_id, browser)
            if response is not None:
                return response
        session = self._active_session(session_id, browser)
        exec_id = self._send_command(session, code)
        return self._wait_for_result(exec_id, session, timeout)

    def _remote_execute(self, code, timeout, session_id, browser):
        response = self._remote_cmd({
            "cmd": "execute_js",
            "sessionId": session_id,
            "browser": browser,
            "code": code,
            "timeout": str(timeout),
        })
        if response is None:
            return None
        result = response.get('r', {})
        if result.get('error'):
            raise RuntimeError(result['error'])
        return result

    def _active_session(self, session_id, browser):
        session = self.sessions.get(session_id)
        if session and session.is_active():
            return session
        time.sleep(3)
        session = self.sessions.get(session_id)
        if session and session.is_active():
            return session
        active = [item for item in self.sessions.values()
                  if item.is_active() and item.browser == browser]
        if not active:
            raise ValueError(f"会话ID {session_id} 未连接")
        session = active[0]
        self.default_session_ids[browser] = session.id
        return session

    def _send_command(self, session, code):
        if session.type not in ('ws', 'http', 'ext_ws'):
            raise ValueError(f"Unsupported session type: {session.type}")
        exec_id = str(uuid.uuid4())
        payload = {'id': exec_id, 'code': code}
        if session.type == 'ext_ws':
            payload['tabId'] = int(session.tab_id)
        message = json.dumps(payload)
        if session.type in ('ws', 'ext_ws'):
            session.ws_client.send_message(message)
        else:
            session.http_queue.put(message)
        self.clean_sessions()
        return exec_id

    def _wait_for_result(self, exec_id, session, timeout):
        started = time.time()
        acknowledged = reloaded = False
        while exec_id not in self.results:
            time.sleep(0.2)
            if not acknowledged and exec_id in self.acks:
                acknowledged, started = True, time.time()
            if session.type in ('ws', 'ext_ws'):
                reloaded = reloaded or not session.is_active()
                if reloaded and session.is_active():
                    return {'result': f"Session {session.id} reloaded.", 'closed': 1}
            if time.time() - started > timeout:
                return self._timeout_result(session, timeout, acknowledged, reloaded)
        result = self.results.pop(exec_id)  
        if exec_id in self.acks: self.acks.pop(exec_id)
        if not result['success']:
            raise RuntimeError(result['data'])
        output = {'data': result['data']}
        new_tabs = result.get('newTabs', [])
        for tab in new_tabs:
            tab.pop('ts', None)
        if new_tabs:
            output['newTabs'] = new_tabs
        return output

    @staticmethod
    def _timeout_result(session, timeout, acknowledged, reloaded):
        if session.type in ('ws', 'ext_ws'):
            if reloaded:
                return {'result': f"Session {session.id} reloaded; the new page is loading.", 'closed': 1}
            state = 'ACK received' if acknowledged else 'no ACK'
            return {'result': f"No response data in {timeout}s ({state})"}
        state = 'delivered' if acknowledged else 'not polled'
        return {'result': f"Session {session.id} no response in {timeout}s ({state})"}
    
    def _remote_cmd(self, cmd):
        try:
            return requests.post(self.remote, headers={"Content-Type": "application/json"},
                                 json=cmd, timeout=float(cmd.get('timeout', 10)) + 20).json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            self._try_takeover()
            if self.is_remote: raise
            return None  # signals caller to retry via local path

    def _try_takeover(self):
        if socket.socket().connect_ex((self.host, self.port + 1)) == 0: return
        try:
            self.start_ws_server()
            self.start_http_server()
        except OSError:
            return  # lost the takeover race to another client, stay remote
        self.is_remote = False
        log("Bridge host died; this process took over as new host")
        deadline = time.time() + 12  # extension probes the port every ~5s
        while time.time() < deadline and not any(s.is_active() for s in self.sessions.values()):
            time.sleep(0.5)

    def resolve_session_id(self, session_id=None, browser=None):
        browser = normalize_browser(browser)
        if session_id is None:
            return self.default_session_ids.get(browser)
        candidate = str(session_id)
        if candidate in self.sessions:
            session = self.sessions[candidate]
            if session.browser != browser:
                raise ValueError(f"Session {candidate} belongs to {session.browser}, not {browser}")
            return candidate
        return session_key(browser, candidate)

    def get_all_sessions(self, browser=None):
        normalized = normalize_browser(browser) if browser is not None else None
        if self.is_remote:
            resp = self._remote_cmd({"cmd": "get_all_sessions", "browser": normalized})
            if resp is not None:
                sessions = resp.get('r', [])
                self._remember_remote_defaults(sessions)
                return sessions
        return [{'id': session.id, **session.info} for session in self.sessions.values()
                if session.is_active() and (normalized is None or session.browser == normalized)]

    def _remember_remote_defaults(self, sessions):
        for session in sessions:
            browser = normalize_browser(session.get('browser'))
            self.default_session_ids.setdefault(browser, str(session['id']))

    def get_session_dict(self):
        return {session['id']: session['url'] for session in self.get_all_sessions()}
        
    def find_session(self, url_pattern: str, browser=None):
        browser = normalize_browser(browser)
        if url_pattern == '': 
            session = self.sessions.get(self.latest_session_ids.get(browser))
            return [(session.id, session.info)] if session else []
        matching_sessions = []  
        for session in self.sessions.values():
            if not session.is_active() or session.browser != browser: continue
            if 'url' in session.info and url_pattern in session.info['url']:  
                matching_sessions.append((session.id, session.info))  
        return matching_sessions

    def set_session(self, url_pattern: str, browser=None):
        browser = normalize_browser(browser)
        if self.is_remote:
            resp = self._remote_cmd({
                "cmd": "find_session", "url_pattern": url_pattern, "browser": browser,
            })
            matched = resp.get('r', []) if resp is not None else self.find_session(url_pattern, browser)
        else:
            matched = self.find_session(url_pattern, browser)
        if not matched:
            log(f"警告: 未找到URL包含 '{url_pattern}' 的会话")
            return None
        if len(matched) > 1:
            log(f"警告: 找到多个URL包含 '{url_pattern}' 的会话，选择第一个")
        session_id, info = matched[0]
        self.default_session_ids[browser] = session_id
        log(f"成功设置 {browser} 默认会话: {session_id}: {info['url']}")
        return session_id
    
    def jump(self, url, timeout=10, browser=None):
        return self.execute_js(f"window.location.href='{url}'", timeout=timeout, browser=browser)

    def newtab(self, url=None, browser=None):
        url = url or "http://www.baidu.com/robots.txt"
        return self.execute_js(f'GM_openInTab("{url}");', browser=browser)
