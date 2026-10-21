"""MediaPipe FaceMesh 封装与关键点索引常量（坐标按图像左右命名）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# 图像左侧的眼睛（A）
EYE_A_OUTER = 33
EYE_A_INNER = 133
EYE_A_UP = 159
EYE_A_DOWN = 145
IRIS_A_CENTER = 468

# 图像右侧的眼睛（B）
EYE_B_INNER = 362
EYE_B_OUTER = 263
EYE_B_UP = 386
EYE_B_DOWN = 374
IRIS_B_CENTER = 473

# EAR 用的 6 点，顺序 p1..p6（p1/p4 为眼角，p2/p3 上眼睑，p5/p6 下眼睑）
EYE_A_EAR = [33, 160, 158, 133, 153, 144]
EYE_B_EAR = [362, 385, 387, 263, 373, 380]

# 头姿 solvePnP 用点
NOSE_TIP = 1
CHIN = 152
MOUTH_A = 61
MOUTH_B = 291

# 面部标定稳定点集（约 20 个）：额头、鼻梁、鼻尖、鼻翼、眼角、嘴角、下巴/上唇
STABLE_POINT_INDEXES = [
    10, 151,            # 额头
    9, 8, 168, 6, 197, 195,  # 眉间与鼻梁
    1, 4, 129, 358,     # 鼻尖与鼻翼
    33, 133, 263, 362,  # 左右眼角
    61, 291,            # 嘴角
    152, 199,           # 下巴与上唇
]

# refine_landmarks=True 时 FaceMesh 输出 478 个点（含虹膜）
FACE_POINT_COUNT = 478
FACE_POINT_COUNT = 478


@dataclass
class FaceLandmarks:
    """一帧人脸关键点：归一化坐标、像素坐标、归一化三维坐标与图像尺寸。"""

    pts_norm: np.ndarray  # (478, 2) 归一化 x,y
    pts_px: np.ndarray  # (478, 2) 像素 x,y
    pts_3d: np.ndarray  # (478, 3) 归一化 x,y,z
    img_w: int
    img_h: int


class LandmarkDetector:
    """MediaPipe FaceMesh 封装；mediapipe 采用延迟导入，方便纯逻辑测试。"""

    def __init__(
        self,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import mediapipe as mp

        self._mp_face_mesh = mp.solutions.face_mesh
        self._mesh = self._mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def detect(self, frame_bgr: np.ndarray) -> Optional[FaceLandmarks]:
        """检测单张人脸；无人脸时返回 None。"""
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        landmarks = result.multi_face_landmarks[0].landmark
        pts_norm = np.array([[point.x, point.y] for point in landmarks], dtype=np.float64)
        pts_3d = np.array([[point.x, point.y, point.z] for point in landmarks], dtype=np.float64)
        pts_px = pts_norm * np.array([width, height], dtype=np.float64)
        return FaceLandmarks(
            pts_norm=pts_norm,
            pts_px=pts_px,
            pts_3d=pts_3d,
            img_w=int(width),
            img_h=int(height),
        )

    def close(self) -> None:
        """释放 MediaPipe 资源。"""
        self._mesh.close()
