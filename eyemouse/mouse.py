"""鼠标控制封装：pyautogui 真实实现与 dry-run 实现，所有调用都容错。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

LOGGER = logging.getLogger(__name__)


class MouseController(ABC):
    """鼠标控制器抽象接口，便于在无桌面环境下替换实现。"""

    @abstractmethod
    def move(self, x: float, y: float) -> None:
        """移动到屏幕坐标 (x, y)。"""

    @abstractmethod
    def click(self, button: str = "left") -> None:
        """单击指定按键。"""

    @abstractmethod
    def double_click(self) -> None:
        """左键双击。"""

    @abstractmethod
    def press(self, button: str = "left") -> None:
        """按下指定按键。"""

    @abstractmethod
    def release(self, button: str = "left") -> None:
        """释放指定按键。"""


class PyAutoGuiMouse(MouseController):
    """真实鼠标控制；每个动作都用 try/except 包裹，异常只记日志不崩溃。"""

    def __init__(self) -> None:
        import pyautogui

        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = False
        self._gui = pyautogui

    def move(self, x: float, y: float) -> None:
        try:
            self._gui.moveTo(int(round(x)), int(round(y)))
        except Exception:
            LOGGER.exception("鼠标移动失败：(%s, %s)", x, y)

    def click(self, button: str = "left") -> None:
        try:
            self._gui.click(button=button)
        except Exception:
            LOGGER.exception("鼠标点击失败：%s", button)

    def double_click(self) -> None:
        try:
            self._gui.doubleClick()
        except Exception:
            LOGGER.exception("鼠标双击失败")

    def press(self, button: str = "left") -> None:
        try:
            self._gui.mouseDown(button=button)
        except Exception:
            LOGGER.exception("鼠标按下失败：%s", button)

    def release(self, button: str = "left") -> None:
        try:
            self._gui.mouseUp(button=button)
        except Exception:
            LOGGER.exception("鼠标释放失败：%s", button)


class DryRunMouse(MouseController):
    """只在日志中记录动作，用于无桌面环境和单元测试。"""

    def move(self, x: float, y: float) -> None:
        LOGGER.info("[dry-run] move(%.0f, %.0f)", x, y)

    def click(self, button: str = "left") -> None:
        LOGGER.info("[dry-run] click(%s)", button)

    def double_click(self) -> None:
        LOGGER.info("[dry-run] double_click()")

    def press(self, button: str = "left") -> None:
        LOGGER.info("[dry-run] press(%s)", button)

    def release(self, button: str = "left") -> None:
        LOGGER.info("[dry-run] release(%s)", button)
