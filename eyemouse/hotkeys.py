"""全局热键：F9 暂停、F10 退出、F8 重校准、F7 点击开关、F6 循环点击模式、F5 切换光标来源、F4 头控基准点。"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import SafetyConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class HotkeyRequests:
    """主循环通过 poll() 取走并清空的热键请求。"""

    toggle_pause: bool = False
    quit: bool = False
    recalibrate: bool = False
    toggle_click: bool = False
    cycle_mode: bool = False
    cycle_cursor: bool = False
    recenter: bool = False

    def any(self) -> bool:
        """是否至少有一个请求。"""
        return (
            self.toggle_pause
            or self.quit
            or self.recalibrate
            or self.toggle_click
            or self.cycle_mode
            or self.cycle_cursor
            or self.recenter
        )


class HotkeyManager:
    """在独立线程监听全局热键，用线程安全的标志位与主循环通信。"""

    def __init__(self, cfg: SafetyConfig) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._requests = HotkeyRequests()
        self._listener: Optional[Any] = None
        self._key_to_request: Dict[Any, str] = {}

    @staticmethod
    def _resolve_key(keyboard: Any, name: str) -> Optional[Any]:
        """把配置里的按键名解析为 pynput 的按键对象。"""
        normalized = name.strip().lower()
        if hasattr(keyboard.Key, normalized):
            return getattr(keyboard.Key, normalized)
        if len(normalized) == 1:
            return keyboard.KeyCode.from_char(normalized)
        LOGGER.warning("无法识别的热键名：%s", name)
        return None

    def _on_press(self, key: Any) -> None:
        request = self._key_to_request.get(key)
        if request is None:
            return
        with self._lock:
            setattr(self._requests, request, True)

    def start(self) -> None:
        """启动热键监听线程。"""
        from pynput import keyboard

        mapping = {
            self.cfg.pause_key: "toggle_pause",
            self.cfg.quit_key: "quit",
            self.cfg.recalibrate_key: "recalibrate",
            self.cfg.toggle_click_key: "toggle_click",
            self.cfg.cycle_mode_key: "cycle_mode",
            self.cfg.cursor_key: "cycle_cursor",
            self.cfg.baseline_key: "recenter",
        }
        self._key_to_request = {}
        for key_name, request_name in mapping.items():
            key = self._resolve_key(keyboard, key_name)
            if key is not None:
                self._key_to_request[key] = request_name
        self._listener = keyboard.Listener(on_press=self._on_press, daemon=True)
        self._listener.start()
        LOGGER.info(
            "热键已注册：%s",
            ", ".join(f"{key}={request}" for key, request in mapping.items()),
        )

    def poll(self) -> HotkeyRequests:
        """取走并清空当前请求。"""
        with self._lock:
            requests = self._requests
            self._requests = HotkeyRequests()
        return requests

    def stop(self) -> None:
        """停止热键监听线程。"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            LOGGER.info("热键监听已停止")
