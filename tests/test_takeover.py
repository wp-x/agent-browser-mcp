"""Regression test: remote client must take over the bridge when the host process dies.

Bug history: is_remote was probed once at __init__ and cached forever, so when the
port-holding host process exited, every remote client failed with ConnectionError
until a brand-new process happened to start. Run: python tests/test_takeover.py
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC)

HOST_CODE = f'''
import sys, time
sys.path.insert(0, "{SRC}")
from agent_browser_mcp.tmwebdriver import TMWebDriver
d = TMWebDriver(host="127.0.0.1", port=18965)
assert not d.is_remote
print("HOST_READY", flush=True)
time.sleep(60)
'''


def main():
    host = subprocess.Popen([sys.executable, "-c", HOST_CODE],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if "HOST_READY" in host.stdout.readline():
                break
        else:
            raise SystemExit("host never became ready")

        from agent_browser_mcp.tmwebdriver import TMWebDriver
        client = TMWebDriver(host="127.0.0.1", port=18965)
        assert client.is_remote, "client should be remote while host is alive"
        assert client.get_all_sessions() == []

        host.kill()
        host.wait()
        time.sleep(0.5)

        result = client.get_all_sessions()  # must trigger takeover, not raise
        assert client.is_remote is False, "client should have taken over as host"
        assert result == []
        assert socket.socket().connect_ex(("127.0.0.1", 18966)) == 0, "http port re-bound"
        print("TAKEOVER_OK")
    finally:
        if host.poll() is None:
            host.kill()


if __name__ == "__main__":
    main()
