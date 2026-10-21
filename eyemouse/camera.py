"""摄像头封装：打开、读帧（统一镜像）、释放；失败时给出中文提示。"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

from .config import CameraConfig

LOGGER = logging.getLogger(__name__)


class CameraError(RuntimeError):
    """摄像头打开失败。"""


class Camera:
    """OpenCV 摄像头封装；镜像在读取时统一处理，其后所有模块都用镜像后的画面。"""

    def __init__(self, cfg: CameraConfig) -> None:
        self.cfg = cfg
        self._capture: Optional[cv2.VideoCapture] = None

    def open(self) -> "Camera":
        """打开摄像头并设置分辨率与帧率。"""
        capture = cv2.VideoCapture(self.cfg.index)
        if not capture.isOpened():
            capture.release()
            raise CameraError(
                f"无法打开摄像头 index={self.cfg.index}，请检查是否被占用或权限不足"
            )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.cfg.width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.cfg.height))
        capture.set(cv2.CAP_PROP_FPS, float(self.cfg.fps))
        self._capture = capture
        LOGGER.info(
            "摄像头已打开：index=%d, %dx%d@%d",
            self.cfg.index,
            self.cfg.width,
            self.cfg.height,
            self.cfg.fps,
        )
        return self

    def read_raw(self) -> Optional[np.ndarray]:
        """读取一帧**未镜像**的原始画面；失败返回 None。

        几何相关处理（摄像头标定、ArUco/PnP）必须使用本接口，避免把未镜像标定参数
        套用到镜像画面上。
        """
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        return frame

    def read(self) -> Optional[np.ndarray]:
        """读取一帧并（按配置）做左右镜像；失败返回 None。

        镜像只用于显示与现有 FaceMesh/Hands 流程；几何处理请用 ``read_raw()``。
        """
        frame = self.read_raw()
        if frame is None:
            return None
        if self.cfg.mirror:
            frame = cv2.flip(frame, 1)
        return frame

    def release(self) -> None:
        """释放摄像头。"""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            LOGGER.info("摄像头已释放")

    @property
    def is_open(self) -> bool:
        """摄像头当前是否可用。"""
        return self._capture is not None and self._capture.isOpened()

    def __enter__(self) -> "Camera":
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
