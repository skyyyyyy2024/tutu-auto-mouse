"""MediaPipe Hands 封装：只取指定手（默认右手）的 21 个关键点。

与 FaceMesh 一样采用延迟导入 mediapipe，便于纯逻辑测试在无 mediapipe 环境下运行。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)

HAND_POINT_COUNT = 21


@dataclass
class HandLandmarks:
    """一帧手部关键点：像素坐标、归一化坐标、左右手标签与置信度。"""

    pts_px: np.ndarray  # (21, 2) 摄像头帧像素坐标
    pts_norm: np.ndarray  # (21, 2) 归一化坐标
    handedness: str  # 校正后的 "Left"/"Right"
    score: float
    img_w: int
    img_h: int


class HandTracker:
    """MediaPipe Hands 封装；detect() 返回指定手的 21 点或 None。"""

    def __init__(
        self,
        max_num_hands: int = 2,
        model_complexity: int = 0,
        mirror_handedness: bool = False,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import mediapipe as mp

        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=int(max_num_hands),
            model_complexity=int(model_complexity),
            min_detection_confidence=float(min_detection_confidence),
            min_tracking_confidence=float(min_tracking_confidence),
        )
        self.mirror_handedness = bool(mirror_handedness)

    def _correct(self, label: str) -> str:
        """按需互换左右手标签（仅在输入画面未镜像时才需要）。"""
        if not self.mirror_handedness:
            return label
        if label == "Left":
            return "Right"
        if label == "Right":
            return "Left"
        return label

    def detect(self, frame_bgr: np.ndarray, want: str = "Right") -> Optional[HandLandmarks]:
        """检测并返回指定手（``want`` 为 "Left"/"Right"/None）；未检出返回 None。"""
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb)
        if not result.multi_hand_landmarks:
            return None
        labels = result.multi_handedness or []
        for index, hand in enumerate(result.multi_hand_landmarks):
            label = ""
            score = 0.0
            if index < len(labels):
                classification = labels[index].classification
                if classification:
                    label = str(classification[0].label)
                    score = float(classification[0].score)
            corrected = self._correct(label)
            if want is not None and corrected != want:
                continue
            landmarks = hand.landmark
            pts_norm = np.array([[point.x, point.y] for point in landmarks], dtype=np.float64)
            pts_px = pts_norm * np.array([width, height], dtype=np.float64)
            return HandLandmarks(
                pts_px=pts_px,
                pts_norm=pts_norm,
                handedness=corrected,
                score=score,
                img_w=int(width),
                img_h=int(height),
            )
        return None

    def close(self) -> None:
        """释放 MediaPipe 资源。"""
        self._hands.close()