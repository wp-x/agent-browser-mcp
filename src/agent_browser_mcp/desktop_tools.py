from __future__ import annotations

from pathlib import Path
from typing import Any


def register_desktop_tools(mcp: Any, root: Path) -> None:
    @mcp.tool(description="Take a desktop screenshot of the primary screen.")
    def capture_desktop_screenshot(save_path: str = "") -> dict[str, Any]:
        import mss
        from PIL import Image

        path = Path(save_path).expanduser().resolve() if save_path else root / "temp_desktop.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            Image.frombytes("RGB", shot.size, shot.rgb).save(path)
        return {"saved_to": str(path), "size": path.stat().st_size}

    @mcp.tool(description="Move the real mouse cursor to screen coordinates.")
    def mouse_move(x: int, y: int, duration: float = 0.0) -> dict[str, Any]:
        import pyautogui

        pyautogui.moveTo(x, y, duration=duration)
        return {"status": "ok", "x": x, "y": y}

    @mcp.tool(description="Click the real desktop at screen coordinates.")
    def mouse_click(
        x: int | None = None,
        y: int | None = None,
        *,
        button: str = "left",
        clicks: int = 1,
        interval: float = 0.1,
    ) -> dict[str, Any]:
        import pyautogui

        pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)
        return {"status": "ok", "x": x, "y": y, "button": button, "clicks": clicks}

    @mcp.tool(description="Drag the real mouse from one point to another.")
    def mouse_drag(
        x1: int,
        y1: int,
        *,
        x2: int,
        y2: int,
        duration: float = 0.3,
        button: str = "left",
    ) -> dict[str, Any]:
        import pyautogui

        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=duration, button=button)
        return {"status": "ok", "from": [x1, y1], "to": [x2, y2], "button": button}

    @mcp.tool(description="Type text via the real keyboard, optionally after clicking a field.")
    def type_text(
        text: str,
        interval: float = 0.01,
        *,
        click_x: int | None = None,
        click_y: int | None = None,
    ) -> dict[str, Any]:
        import pyautogui

        if click_x is not None and click_y is not None:
            pyautogui.click(click_x, click_y)
        pyautogui.write(text, interval=interval)
        return {"status": "ok", "typed_chars": len(text)}

    @mcp.tool(description="Send a hotkey chord like 'command,l' or 'ctrl,shift,p'.")
    def hotkey(keys_csv: str) -> dict[str, Any]:
        import pyautogui

        keys = [key.strip() for key in keys_csv.split(",") if key.strip()]
        if not keys:
            raise RuntimeError("keys_csv must contain at least one key")
        pyautogui.hotkey(*keys)
        return {"status": "ok", "keys": keys}

    @mcp.tool(description="Report the current desktop pointer and primary screen size.")
    def pointer_info() -> dict[str, Any]:
        import pyautogui

        x, y = pyautogui.position()
        width, height = pyautogui.size()
        return {"x": x, "y": y, "screen_width": width, "screen_height": height}
