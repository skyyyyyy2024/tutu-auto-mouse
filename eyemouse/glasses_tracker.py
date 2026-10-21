"""眼镜 ArUco 标记的六自由度追踪（阶段一：只输出位姿，不接管鼠标）。

要点：
- 只使用**未镜像**的原始画面做几何计算；镜像只用于显示。
- 平面单标记用 ``solvePnPGeneric`` + ``SOLVEPNP_IPPE_SQUARE``，模型点顺序严格按 OpenCV 要求。
- 原则是**先判断是否可信，再平滑**：不靠重滤波掩盖错误位姿。
- 旋转用四元数（符号连续 + SLERP），平移用独立滤波状态；欧拉角只用于显示。
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)

# 失效状态
NO_MARKER = "NO_MARKER"
TOO_SMALL = "TOO_SMALL"
AMBIGUOUS = "AMBIGUOUS"
BAD_REPROJECTION = "BAD_REPROJECTION"
MOTION_OUTLIER = "MOTION_OUTLIER"
CALIBRATION_MISMATCH = "CALIBRATION_MISMATCH"
STABILIZING = "STABILIZING"
TRACKING = "TRACKING"

STATUSES = (
    NO_MARKER,
    TOO_SMALL,
    AMBIGUOUS,
    BAD_REPROJECTION,
    MOTION_OUTLIER,
    CALIBRATION_MISMATCH,
    STABILIZING,
    TRACKING,
)


def marker_object_points(marker_size_m: float) -> np.ndarray:
    """IPPE_SQUARE 要求的模型点顺序（Y 轴向上，单位米）。

    顺序：左上(-s/2,+s/2,0) → 右上(+s/2,+s/2,0) → 右下(+s/2,-s/2,0) → 左下(-s/2,-s/2,0)，
    与 ``cv2.aruco.detectMarkers`` 返回的角点顺序（图像左上→右上→右下→左下）一一对应。
    """
    half = float(marker_size_m) / 2.0
    return np.array(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np.float32,
    )


def rotation_matrix_from_rvec(rvec: np.ndarray) -> np.ndarray:
    """罗德里格斯向量 → 3x3 旋转矩阵。"""
    matrix, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    return np.asarray(matrix, dtype=np.float64)


def is_valid_rotation(matrix: np.ndarray, tolerance: float = 1e-3) -> bool:
    """检查是否为正交且行列式为 +1 的旋转矩阵。"""
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        return False
    should_be_identity = matrix.T @ matrix
    if not np.allclose(should_be_identity, np.eye(3), atol=tolerance):
        return False
    return abs(float(np.linalg.det(matrix)) - 1.0) <= tolerance


def quaternion_from_matrix(matrix: np.ndarray) -> np.ndarray:
    """旋转矩阵 → 规范化四元数 (w, x, y, z)。"""
    matrix = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.array(
            [
                0.25 * scale,
                (matrix[2, 1] - matrix[1, 2]) / scale,
                (matrix[0, 2] - matrix[2, 0]) / scale,
                (matrix[1, 0] - matrix[0, 1]) / scale,
            ]
        )
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (matrix[2, 1] - matrix[1, 2]) / scale,
                    0.25 * scale,
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                ]
            )
        elif index == 1:
            scale = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (matrix[0, 2] - matrix[2, 0]) / scale,
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    0.25 * scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                ]
            )
        else:
            scale = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quaternion = np.array(
                [
                    (matrix[1, 0] - matrix[0, 1]) / scale,
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                    0.25 * scale,
                ]
            )
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0 or not math.isfinite(norm):
        return np.array([1.0, 0.0, 0.0, 0.0])
    return quaternion / norm


def quaternion_dot(q1: np.ndarray, q2: np.ndarray) -> float:
    """四元数点积（同号表示短弧）。"""
    return float(np.dot(np.asarray(q1, dtype=np.float64), np.asarray(q2, dtype=np.float64)))


def align_quaternion_sign(quaternion: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """把四元数符号调整到与参考四元数同半球（q 与 -q 表示同一旋转）。"""
    quaternion = np.asarray(quaternion, dtype=np.float64)
    if quaternion_dot(quaternion, reference) < 0.0:
        return -quaternion
    return quaternion


def quaternion_angle_deg(q1: np.ndarray, q2: np.ndarray) -> float:
    """两个四元数之间的旋转夹角（度）；符号无关。"""
    dot = abs(quaternion_dot(q1, q2))
    dot = max(min(dot, 1.0), -1.0)
    return math.degrees(2.0 * math.acos(dot))


def rotation_angle_deg(matrix_a: np.ndarray, matrix_b: np.ndarray) -> float:
    """两个旋转矩阵之间的夹角（度），使用旋转几何而非欧拉角相减。"""
    relative = np.asarray(matrix_a, dtype=np.float64).T @ np.asarray(matrix_b, dtype=np.float64)
    cosine = (float(np.trace(relative)) - 1.0) / 2.0
    cosine = max(min(cosine, 1.0), -1.0)
    return math.degrees(math.acos(cosine))


def slerp(q0: np.ndarray, q1: np.ndarray, alpha: float) -> np.ndarray:
    """球面线性插值；alpha<=0 返回 q0，alpha>=1 返回 q1。"""
    q0 = np.asarray(q0, dtype=np.float64)
    q1 = align_quaternion_sign(np.asarray(q1, dtype=np.float64), q0)
    alpha = float(alpha)
    if alpha <= 0.0:
        return q0
    if alpha >= 1.0:
        return q1 / max(float(np.linalg.norm(q1)), 1e-12)
    dot = max(min(quaternion_dot(q0, q1), 1.0), -1.0)
    if dot > 0.9995:
        blended = q0 + alpha * (q1 - q0)
        return blended / max(float(np.linalg.norm(blended)), 1e-12)
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    if abs(sin_theta) < 1e-12:
        return q0
    weight0 = math.sin((1.0 - alpha) * theta) / sin_theta
    weight1 = math.sin(alpha * theta) / sin_theta
    return weight0 * q0 + weight1 * q1


def direction_angles_deg(matrix: np.ndarray) -> Tuple[float, float, float]:
    """`(yaw, pitch, roll)`，仅供显示；基准是“标记正面正对摄像头”（此时三个角都是 0）。

    - yaw   = 标记法向朝图像右侧偏转的角度（左右摇头），向右为正
    - pitch = 标记法向朝图像上方偏转的角度（抬头为正）
    - roll  = 标记平面内绕法向的旋转（歪头）

    标记坐标系的 +Z 指向摄像头（即标记正面），正对摄像头时法向为 (0, 0, -1)，
    因此基准方向取 ``-normal_z`` 才能让“正对摄像头”显示成 0 度。
    """
    matrix = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    normal = matrix[:, 2]
    forward_z = -float(normal[2])
    yaw = math.degrees(math.atan2(float(normal[0]), forward_z))
    horizontal = math.hypot(float(normal[0]), forward_z)
    pitch = math.degrees(math.atan2(-float(normal[1]), max(horizontal, 1e-12)))
    roll = math.degrees(math.atan2(float(matrix[1, 0]), float(matrix[0, 0])))
    return (yaw, pitch, roll)


@dataclass
class PoseCandidate:
    """一个候选位姿。"""

    rotation: np.ndarray
    translation: np.ndarray
    reprojection_error_px: float
    positive_depth: bool
    valid_rotation: bool

    @property
    def acceptable(self) -> bool:
        """是否通过基本质量检查。"""
        return self.positive_depth and self.valid_rotation and math.isfinite(self.reprojection_error_px)


@dataclass
class GlassesPose:
    """一帧的追踪结果。"""

    valid: bool
    status: str
    timestamp: float
    marker_id: int = -1
    stale: bool = False
    reason: str = ""
    corners_px: Optional[np.ndarray] = None
    marker_area_px: Optional[float] = None
    reprojection_error_px: Optional[float] = None
    rotation_matrix: Optional[np.ndarray] = None
    translation_m: Optional[np.ndarray] = None
    quaternion: Optional[np.ndarray] = None
    raw_rotation_matrix: Optional[np.ndarray] = None
    raw_translation_m: Optional[np.ndarray] = None
    raw_quaternion: Optional[np.ndarray] = None
    resolve_note: str = ""

    def angles_deg(self) -> Optional[Tuple[float, float, float]]:
        """平滑后的 (yaw, pitch, roll)，单位度；无位姿返回 None。"""
        if self.rotation_matrix is None:
            return None
        return direction_angles_deg(self.rotation_matrix)

    def translation_mm(self) -> Optional[Tuple[float, float, float]]:
        """平移的毫米表示，便于阅读。"""
        if self.translation_m is None:
            return None
        return tuple(float(v) * 1000.0 for v in np.asarray(self.translation_m).ravel())


@dataclass
class _AmbiguityBranch:
    """平面标记双解歧义的一支：按旋转连续性把多帧观测归并到同一解。"""

    rotation: np.ndarray
    sum_error: float = 0.0
    count: int = 0
    wins: int = 0
    last: Optional[PoseCandidate] = None

    @property
    def mean_error(self) -> float:
        """该支候选的多帧平均重投影 RMS（像素）。"""
        return 0.0 if self.count <= 0 else self.sum_error / float(self.count)


@dataclass
class GlassesStats:
    """追踪质量统计。"""

    frames: int = 0
    tracking_frames: int = 0
    status_counts: Dict[str, int] = field(default_factory=dict)
    _tracking_times: Deque[float] = field(default_factory=lambda: deque(maxlen=120), repr=False)

    def note(self, status: str, timestamp: float) -> None:
        """记录一帧状态。"""
        self.frames += 1
        self.status_counts[status] = self.status_counts.get(status, 0) + 1
        if status == TRACKING:
            self.tracking_frames += 1
            self._tracking_times.append(float(timestamp))

    def valid_ratio(self) -> float:
        """TRACKING 帧占比。"""
        return 0.0 if self.frames == 0 else self.tracking_frames / float(self.frames)

    def tracking_fps(self) -> float:
        """最近若干有效观测推算的帧率。"""
        if len(self._tracking_times) < 2:
            return 0.0
        span = self._tracking_times[-1] - self._tracking_times[0]
        if span <= 0.0:
            return 0.0
        return (len(self._tracking_times) - 1) / span

    def reset(self) -> None:
        """清零统计。"""
        self.frames = 0
        self.tracking_frames = 0
        self.status_counts.clear()
        self._tracking_times.clear()


@dataclass
class StabilityStats:
    """静止稳定性统计：平移标准差（mm）与相对参考的旋转夹角统计（度）。"""

    window_s: float = 10.0
    translations_m: Deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=600), repr=False)
    times: Deque[float] = field(default_factory=lambda: deque(maxlen=600), repr=False)
    angles_deg: Deque[float] = field(default_factory=lambda: deque(maxlen=600), repr=False)
    reference_quaternion: Optional[np.ndarray] = None

    def reset(self) -> None:
        """清空窗口与参考姿态。"""
        self.translations_m.clear()
        self.times.clear()
        self.angles_deg.clear()
        self.reference_quaternion = None

    def push(self, timestamp: float, translation_m: np.ndarray, quaternion: np.ndarray) -> None:
        """加入一个有效观测（只应对 TRACKING 帧调用）。"""
        self._drop_old(float(timestamp))
        if self.reference_quaternion is None:
            self.reference_quaternion = np.asarray(quaternion, dtype=np.float64)
        self.times.append(float(timestamp))
        self.translations_m.append(np.asarray(translation_m, dtype=np.float64).reshape(3))
        self.angles_deg.append(quaternion_angle_deg(self.reference_quaternion, quaternion))

    def _drop_old(self, timestamp: float) -> None:
        while self.times and timestamp - self.times[0] > float(self.window_s):
            self.times.popleft()
            self.translations_m.popleft()
            self.angles_deg.popleft()

    def summary(self) -> Dict[str, float]:
        """返回 position_std_mm 与 rotation_std_deg / rotation_mean_deg（角度用旋转几何，不跨 ±180°）。"""
        if len(self.translations_m) < 2:
            return {
                "samples": float(len(self.translations_m)),
                "position_std_mm": 0.0,
                "rotation_mean_deg": 0.0,
                "rotation_std_deg": 0.0,
                "span_s": 0.0,
            }
        stacked = np.stack(list(self.translations_m), axis=0)
        std_m = np.std(stacked, axis=0)
        position_std_mm = float(np.linalg.norm(std_m) * 1000.0)
        angles = np.asarray(list(self.angles_deg), dtype=np.float64)
        span = float(self.times[-1] - self.times[0])
        return {
            "samples": float(len(angles)),
            "position_std_mm": position_std_mm,
            "rotation_mean_deg": float(np.mean(angles)),
            "rotation_std_deg": float(np.std(angles)),
            "span_s": span,
        }


class GlassesTracker:
    """单标记眼镜追踪器。"""

    def __init__(self, cfg: Any, calibration: Any) -> None:
        self.cfg = cfg
        self.calibration = calibration
        self.marker_id = int(getattr(cfg, "marker_id", 0))
        self.marker_size_m = float(getattr(cfg, "marker_size_m", 0.03))
        self.object_points = marker_object_points(self.marker_size_m)
        self.stats = GlassesStats()
        self.criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.01,
        )
        self._dictionary = self._resolve_dictionary(str(getattr(cfg, "dictionary", "DICT_5X5_50")))
        self._detector = cv2.aruco.ArucoDetector(self._dictionary, cv2.aruco.DetectorParameters())
        self.reset()

    @staticmethod
    def _resolve_dictionary(name: str) -> Any:
        if not hasattr(cv2.aruco, name):
            raise ValueError(f"未知的 ArUco 字典名：{name}")
        return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))

    # ---------------- 状态 ----------------
    def reset(self) -> None:
        """清空滤波与连续性状态（不清理累计统计）。"""
        self._previous_rotation: Optional[np.ndarray] = None
        self._previous_translation: Optional[np.ndarray] = None
        self._previous_time: Optional[float] = None
        self._smoothed_quaternion: Optional[np.ndarray] = None
        self._smoothed_translation: Optional[np.ndarray] = None
        self._trusted = False
        self._valid_streak = 0
        self._last_valid_time: Optional[float] = None
        self._last_pose: Optional[GlassesPose] = None
        self._ambiguity_branches: List[_AmbiguityBranch] = []
        self._ambiguity_frames = 0

    def reset_stats(self) -> None:
        """清空统计。"""
        self.stats.reset()

    # ---------------- 检测 ----------------
    def detect_marker(self, gray: np.ndarray) -> Optional[np.ndarray]:
        """检测目标标记并做亚像素精化，返回 (4,2) float32 角点；未检出返回 None。"""
        try:
            corners_list, ids, _rejected = self._detector.detectMarkers(gray)
        except cv2.error as exc:
            LOGGER.debug("标记检测失败：%s", exc)
            return None
        if ids is None or len(ids) == 0:
            return None
        for index, marker_id in enumerate(np.asarray(ids).ravel()):
            if int(marker_id) != self.marker_id:
                continue
            corners = np.asarray(corners_list[index], dtype=np.float32).reshape(-1, 1, 2)
            window = max(int(getattr(self.cfg, "subpixel_win", 5)), 1)
            half = (window, window)
            try:
                refined = cv2.cornerSubPix(gray, corners.copy(), half, (-1, -1), self.criteria)
            except cv2.error:  # pragma: no cover - 极端图像尺寸下的保护
                refined = corners
            return np.asarray(refined, dtype=np.float32).reshape(4, 2)
        return None

    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        """把输入帧转成 8 位灰度图；支持已灰度、3 通道与 4 通道（BGRA）。"""
        if frame is None:
            raise ValueError("输入帧为空")
        if frame.dtype != np.uint8:
            raise ValueError(f"不支持的像素类型：{frame.dtype}")
        if frame.ndim == 2:
            return frame
        if frame.ndim != 3 or frame.shape[2] not in (3, 4):
            raise ValueError(f"不支持的帧形状：{frame.shape}")
        code = cv2.COLOR_BGR2GRAY if frame.shape[2] == 3 else cv2.COLOR_BGRA2GRAY
        return cv2.cvtColor(frame, code)

    # ---------------- 位姿 ----------------
    def solve_candidates(self, corners_px: np.ndarray) -> List[PoseCandidate]:
        """用 IPPE_SQUARE 求解候选位姿，并做正深度/旋转有效性/重投影检查。"""
        camera_matrix = np.asarray(self.calibration.camera_matrix, dtype=np.float64)
        dist_coeffs = np.asarray(self.calibration.dist_coeffs, dtype=np.float64)
        image_points = np.asarray(corners_px, dtype=np.float32).reshape(-1, 1, 2)
        if not np.all(np.isfinite(image_points)):
            return []
        try:
            retval, rvecs, tvecs, reprojection = cv2.solvePnPGeneric(
                self.object_points,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,
            )
        except cv2.error as exc:
            LOGGER.debug("solvePnPGeneric 失败：%s", exc)
            return []
        candidates: List[PoseCandidate] = []
        for index in range(int(retval)):
            rotation = rotation_matrix_from_rvec(np.asarray(rvecs[index]))
            translation = np.asarray(tvecs[index], dtype=np.float64).reshape(3)
            error = float(np.asarray(reprojection[index]).ravel()[0])
            candidates.append(
                PoseCandidate(
                    rotation=rotation,
                    translation=translation,
                    reprojection_error_px=error,
                    positive_depth=bool(translation[2] > 0.0),
                    valid_rotation=is_valid_rotation(rotation),
                )
            )
        return candidates

    def select_candidate(
        self, candidates: Sequence[PoseCandidate], timestamp: Optional[float] = None
    ) -> Tuple[Optional[PoseCandidate], str, str]:
        """选择可信候选；返回 ``(候选, 状态, 说明)``。

        - 只有通过正深度、旋转有效性、重投影阈值检查的候选才参与选择。
        - 两个候选重投影误差差距明显，或几何上几乎等价（夹角小于 ``ambiguity_angle_deg``）时，
          直接取误差更小的解。
        - 真正的平面标记双解歧义：先按时间连续性择一；没有近期参考时累积多帧重投影证据判定。
          证据仍不足则返回 ``(None, AMBIGUOUS, 说明)``，不强行输出可信姿态。
        """
        limit = float(getattr(self.cfg, "max_reprojection_error_px", 3.0))
        quality = [c for c in candidates if c.acceptable and c.reprojection_error_px <= limit]
        if not quality:
            if candidates:
                return None, BAD_REPROJECTION, self._reason_text(BAD_REPROJECTION)
            return None, NO_MARKER, self._reason_text(NO_MARKER)
        quality.sort(key=lambda c: c.reprojection_error_px)
        best = quality[0]
        if len(quality) == 1:
            return best, "", ""
        second = quality[1]
        margin = float(getattr(self.cfg, "ambiguity_reproj_margin_px", 0.5))
        angle_limit = float(getattr(self.cfg, "ambiguity_angle_deg", 12.0))
        close = abs(second.reprojection_error_px - best.reprojection_error_px) <= margin
        far = rotation_angle_deg(best.rotation, second.rotation) >= angle_limit
        if not (close and far):
            return best, "", ""
        # 连续性只用于在都通过质量检查的候选之间择一，不覆盖质量检查。
        resolved = self._resolve_by_continuity(quality, timestamp)
        if resolved is not None:
            return resolved, "", "在合格候选之间按时间连续性择一（平面标记双解）"
        resolved = self._accumulate_ambiguity(quality)
        if resolved is not None:
            return resolved, "", "已用多帧重投影证据消除平面标记双解歧义"
        need = int(getattr(self.cfg, "acquisition_frames", 20))
        note = (
            f"平面标记存在双解歧义：正在累积多帧证据判定（{self._ambiguity_frames}/{need}），"
            "请保持标记可见并尽量静止，或轻微左右转动头部"
        )
        return None, AMBIGUOUS, note

    def _resolve_by_continuity(
        self, candidates: Sequence[PoseCandidate], timestamp: Optional[float] = None
    ) -> Optional[PoseCandidate]:
        """有近期参考姿态时按旋转连续性择一；否则返回 None（不含糊地猜）。"""
        if self._previous_rotation is None or self._previous_time is None or timestamp is None:
            return None
        gap = float(timestamp) - float(self._previous_time)
        if not math.isfinite(gap) or gap < 0.0:
            return None
        if gap > float(getattr(self.cfg, "gap_reset_s", 0.5)):
            return None
        return min(candidates, key=lambda c: rotation_angle_deg(self._previous_rotation, c.rotation))

    def _accumulate_ambiguity(self, quality: Sequence[PoseCandidate]) -> Optional[PoseCandidate]:
        """把本帧合格候选并入歧义分支，累积多帧证据；证据足够时返回胜出候选，否则 None。"""
        tolerance = float(getattr(self.cfg, "ambiguity_branch_angle_deg", 25.0))
        # 一支每帧最多接收一个候选：否则同一帧的双解会被并进同一支，歧义永远无法分开。
        pairs = []
        for candidate_index, candidate in enumerate(quality):
            for branch_index, branch in enumerate(self._ambiguity_branches):
                pairs.append(
                    (rotation_angle_deg(branch.rotation, candidate.rotation), candidate_index, branch_index)
                )
        pairs.sort(key=lambda item: item[0])
        taken_candidates: set = set()
        taken_branches: set = set()
        assignment: Dict[int, int] = {}
        for angle, candidate_index, branch_index in pairs:
            if angle > tolerance:
                break
            if candidate_index in taken_candidates or branch_index in taken_branches:
                continue
            taken_candidates.add(candidate_index)
            taken_branches.add(branch_index)
            assignment[candidate_index] = branch_index
        for candidate_index, candidate in enumerate(quality):
            branch_index = assignment.get(candidate_index)
            if branch_index is None:
                self._ambiguity_branches.append(_AmbiguityBranch(rotation=candidate.rotation.copy()))
                branch_index = len(self._ambiguity_branches) - 1
            target = self._ambiguity_branches[branch_index]
            target.rotation = candidate.rotation.copy()
            target.sum_error += float(candidate.reprojection_error_px)
            target.count += 1
            target.last = candidate
        matched = [self._ambiguity_branches[index] for index in set(assignment.values())]
        if matched:
            winner = min(matched, key=lambda branch: branch.last.reprojection_error_px)
            winner.wins += 1
        self._ambiguity_frames += 1
        need = int(getattr(self.cfg, "acquisition_frames", 20))
        if self._ambiguity_frames < need:
            return None
        floor = max(1, self._ambiguity_frames // 2)
        usable = [
            branch
            for branch in self._ambiguity_branches
            if branch.count >= floor and branch.last is not None
        ]
        if not usable:
            return None
        usable.sort(key=lambda b: b.mean_error)
        if len(usable) == 1:
            # 只有一支在持续出现：另一解已被质量检查淘汰，可以直接采用。
            if usable[0].count >= int(need * 0.8):
                self._clear_ambiguity()
                return usable[0].last
            return None
        better, worse = usable[0], usable[1]
        # 双解误差接近时单帧无法区分；要求"平均误差明显更低"且"多数帧都是它更优"两条证据同时成立。
        margin_ok = worse.mean_error - better.mean_error >= float(
            getattr(self.cfg, "ambiguity_evidence_px", 0.15)
        )
        dominance_ok = better.wins >= 0.75 * float(better.count)
        if margin_ok and dominance_ok:
            self._clear_ambiguity()
            return better.last
        return None

    def _clear_ambiguity(self) -> None:
        """清空歧义证据累积。"""
        self._ambiguity_branches = []
        self._ambiguity_frames = 0

    # ---------------- 主入口 ----------------
    def update(self, frame_bgr: np.ndarray, now: float) -> GlassesPose:
        """处理一帧（**未镜像**原始画面），返回本帧位姿结果。"""
        timestamp = float(now)
        if self.calibration is None:
            return self._invalid(CALIBRATION_MISMATCH, timestamp, "缺少摄像头内参文件，请先运行 --calibrate-camera")
        if frame_bgr is None:
            return self._invalid(NO_MARKER, timestamp, "未收到有效画面（读取失败）")
        width, height = int(frame_bgr.shape[1]), int(frame_bgr.shape[0])
        expected = (int(self.calibration.image_size[0]), int(self.calibration.image_size[1]))
        if (width, height) != expected:
            return self._invalid(
                CALIBRATION_MISMATCH,
                timestamp,
                f"运行分辨率 {width}x{height} 与标定分辨率 {expected[0]}x{expected[1]} 不一致，请重新标定",
            )
        try:
            gray = self._to_gray(frame_bgr)
        except (ValueError, cv2.error):
            return self._invalid(NO_MARKER, timestamp, "本帧画面无法处理（通道数或数值非法）")
        corners = self.detect_marker(gray)
        if corners is None:
            return self._invalid(NO_MARKER, timestamp, "未检测到目标标记")
        if not np.all(np.isfinite(corners)):
            return self._invalid(NO_MARKER, timestamp, "检测到的角点含非有限值，已丢弃该帧")

        area = float(abs(cv2.contourArea(corners.reshape(-1, 2).astype(np.float32))))
        if area < float(getattr(self.cfg, "min_marker_area_px", 400.0)):
            return self._invalid(TOO_SMALL, timestamp, f"标记面积过小（{area:.0f}px²）", corners=corners, area=area)

        candidates = self.solve_candidates(corners)
        chosen, reason, note = self.select_candidate(candidates, timestamp)
        if chosen is None:
            return self._invalid(
                reason, timestamp, note or self._reason_text(reason), corners=corners, area=area
            )

        reject = self._check_motion(chosen, timestamp)
        if reject is not None:
            return self._invalid(reject, timestamp, self._reason_text(reject), corners=corners, area=area)

        self._valid_streak += 1
        # 注意：这里不能再看 _trusted，否则 _trusted 只在非 stabilizing 分支置位 -> 永远进不了 TRACKING。
        stabilizing = self._valid_streak < int(getattr(self.cfg, "stabilize_frames", 5))
        if stabilizing:
            self._remember_raw(chosen, timestamp)
            status = STABILIZING
            pose = self._make_pose(
                status=status,
                valid=False,
                timestamp=timestamp,
                chosen=chosen,
                corners=corners,
                area=area,
                reason=f"正在稳定（{self._valid_streak}/{int(getattr(self.cfg, 'stabilize_frames', 5))}）",
                note=note,
            )
            self.stats.note(status, timestamp)
            self._last_pose = pose
            return pose

        self._smooth(chosen)
        self._trusted = True
        self._last_valid_time = timestamp
        pose = self._make_pose(
            status=TRACKING,
            valid=True,
            timestamp=timestamp,
            chosen=chosen,
            corners=corners,
            area=area,
            note=note,
        )
        self.stats.note(TRACKING, timestamp)
        self._remember_raw(chosen, timestamp)
        self._last_pose = pose
        return pose

    # ---------------- 内部 ----------------
    def _reason_text(self, status: str) -> str:
        return {
            NO_MARKER: "未检测到目标标记",
            TOO_SMALL: "标记面积过小",
            AMBIGUOUS: "候选位姿存在无法可靠区分的歧义，暂不输出可信姿态",
            BAD_REPROJECTION: "重投影误差超阈值",
            MOTION_OUTLIER: "运动超阈值或时间戳异常",
            CALIBRATION_MISMATCH: "内参与运行分辨率不匹配",
        }.get(status, status)

    def _check_motion(self, chosen: PoseCandidate, timestamp: float) -> Optional[str]:
        """速度/角速度异常拒绝（真实时间戳）。返回拒绝状态或 None。"""
        if self._previous_time is None or self._previous_rotation is None or self._previous_translation is None:
            return None
        delta_t = timestamp - self._previous_time
        if not math.isfinite(delta_t) or delta_t <= 0.0:
            return MOTION_OUTLIER
        if delta_t > float(getattr(self.cfg, "gap_reset_s", 0.5)):
            # 长时间间隔后不沿用旧速度判据，直接重置连续性状态
            self._reset_motion_state()
            return None
        linear = float(np.linalg.norm(chosen.translation - self._previous_translation)) / delta_t
        angular = rotation_angle_deg(self._previous_rotation, chosen.rotation) / delta_t
        if linear > float(getattr(self.cfg, "max_linear_speed_m_s", 1.5)):
            return MOTION_OUTLIER
        if angular > float(getattr(self.cfg, "max_angular_speed_deg_s", 400.0)):
            return MOTION_OUTLIER
        return None

    def _reset_motion_state(self) -> None:
        """重置速度/滤波连续性，避免从丢失前一帧缓慢滑回。"""
        self._previous_rotation = None
        self._previous_translation = None
        self._smoothed_quaternion = None
        self._smoothed_translation = None
        self._trusted = False
        self._valid_streak = 0
        self._clear_ambiguity()

    def _remember_raw(self, chosen: PoseCandidate, timestamp: float) -> None:
        self._previous_rotation = chosen.rotation
        self._previous_translation = chosen.translation
        self._previous_time = timestamp

    def _smooth(self, chosen: PoseCandidate) -> None:
        raw_quaternion = quaternion_from_matrix(chosen.rotation)
        if self._smoothed_quaternion is None or self._smoothed_translation is None:
            self._smoothed_quaternion = raw_quaternion
            self._smoothed_translation = chosen.translation
            return
        alpha = float(getattr(self.cfg, "slerp_alpha", 0.35))
        self._smoothed_quaternion = slerp(self._smoothed_quaternion, raw_quaternion, alpha)
        translation_alpha = float(getattr(self.cfg, "translation_alpha", 0.35))
        self._smoothed_translation = self._smoothed_translation + translation_alpha * (
            chosen.translation - self._smoothed_translation
        )

    def _make_pose(
        self,
        status: str,
        valid: bool,
        timestamp: float,
        chosen: Optional[PoseCandidate],
        corners: Optional[np.ndarray] = None,
        area: Optional[float] = None,
        reason: str = "",
        note: str = "",
    ) -> GlassesPose:
        pose = GlassesPose(
            valid=valid,
            status=status,
            timestamp=timestamp,
            marker_id=self.marker_id,
            reason=reason,
            resolve_note=note,
            corners_px=None if corners is None else np.asarray(corners, dtype=np.float64).reshape(4, 2),
            marker_area_px=area,
        )
        if chosen is not None:
            pose.raw_rotation_matrix = chosen.rotation
            pose.raw_translation_m = chosen.translation
            pose.raw_quaternion = quaternion_from_matrix(chosen.rotation)
            pose.reprojection_error_px = float(chosen.reprojection_error_px)
            if self._smoothed_quaternion is not None:
                pose.rotation_matrix = _quaternion_to_matrix(self._smoothed_quaternion)
                pose.quaternion = self._smoothed_quaternion
                pose.translation_m = self._smoothed_translation
            else:
                pose.rotation_matrix = chosen.rotation
                pose.quaternion = pose.raw_quaternion
                pose.translation_m = chosen.translation
        return pose

    def _invalid(
        self,
        status: str,
        timestamp: float,
        reason: str,
        corners: Optional[np.ndarray] = None,
        area: Optional[float] = None,
    ) -> GlassesPose:
        """失效帧：立即判定当前观测无效；UI 可显示 stale 的最后姿态。"""
        self.stats.note(status, timestamp)
        if status != AMBIGUOUS:
            self._valid_streak = 0
            self._trusted = False
            self._smoothed_quaternion = None
            self._smoothed_translation = None
            self._previous_rotation = None
            self._previous_translation = None
            self._clear_ambiguity()
        pose = GlassesPose(
            valid=False,
            status=status,
            timestamp=timestamp,
            marker_id=self.marker_id,
            reason=reason,
            corners_px=None if corners is None else np.asarray(corners, dtype=np.float64).reshape(4, 2),
            marker_area_px=area,
        )
        stale_limit = float(getattr(self.cfg, "stale_timeout_s", 0.5))
        if self._last_pose is not None and self._last_valid_time is not None:
            if timestamp - self._last_valid_time <= stale_limit and self._last_pose.rotation_matrix is not None:
                pose.stale = True
                pose.rotation_matrix = self._last_pose.rotation_matrix
                pose.translation_m = self._last_pose.translation_m
                pose.quaternion = self._last_pose.quaternion
                pose.raw_rotation_matrix = self._last_pose.raw_rotation_matrix
                pose.raw_translation_m = self._last_pose.raw_translation_m
                pose.raw_quaternion = self._last_pose.raw_quaternion
        self._last_pose = pose
        return pose


def _quaternion_to_matrix(quaternion: np.ndarray) -> np.ndarray:
    """规范化四元数 (w,x,y,z) → 3x3 旋转矩阵。"""
    w, x, y, z = (float(v) for v in np.asarray(quaternion, dtype=np.float64).ravel())
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm <= 0.0:
        return np.eye(3)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
