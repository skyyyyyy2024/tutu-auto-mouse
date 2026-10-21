"""9 点校准流程、Ridge 回归模型、JSON 保存/加载与眨眼练习。"""

from __future__ import annotations

import json
import logging
import math
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from .click_detector import ClickDetector
from .config import AppConfig
from .features import (
    DEG_PER_UNIT,
    FEATURE_DIM,
    HEAD_POSE_SLICE,
    HEAD_SCALE_INDEX,
    build_feature_vector,
    compute_ear,
)
from .face_profile import FaceProfile, FaceProfiler
from .head_pose import HeadPoseEstimator

LOGGER = logging.getLogger(__name__)

MODEL_VERSION = 3
ESC_KEY = 27
BASELINE_SECONDS = 1.5
MIN_VALID_FRAMES = 10
MIN_POINT_SAMPLES = 10
MIN_HEAD_POINT_SAMPLES = 5
PRACTICE_TIMEOUT = 6.0

# 头动阶段样本的点编号从该偏移量开始，避免与 9 点静止样本混在一起
HEAD_MOTION_POINT_ID_OFFSET = 100
KIND_STATIC = "static"
KIND_HEAD = "head"

POSE_FIELDS = ("yaw", "pitch", "roll", "scale")


def _normalize_pose_range(value: Any) -> Optional[Dict[str, Tuple[float, float]]]:
    """把 JSON/字典形式的头姿范围统一成 {字段: (min, max)}。"""
    if not value:
        return None
    result: Dict[str, Tuple[float, float]] = {}
    for name in POSE_FIELDS:
        bounds = value.get(name)
        if bounds is None:
            continue
        low, high = float(bounds[0]), float(bounds[1])
        result[name] = (min(low, high), max(low, high))
    return result or None


def _pose_range_to_json(value: Optional[Dict[str, Tuple[float, float]]]) -> Optional[dict]:
    """把头姿范围转换为可 JSON 序列化的 {字段: [min, max]}。"""
    if not value:
        return None
    return {name: [float(bounds[0]), float(bounds[1])] for name, bounds in value.items()}


class ScreenSizeMismatchError(ValueError):
    """校准文件记录的分辨率与当前屏幕不一致。"""


class ModelVersionMismatchError(ValueError):
    """校准文件版本与当前模型不兼容，需要重新校准。"""


class CalibrationCancelled(Exception):
    """用户按 ESC 取消校准或跳过练习。"""


def _call_ui(ui: Any, name: str, *args: Any) -> Any:
    """调用 UI 对象上的可选方法；UI 未实现该方法时返回 None。"""
    callback = getattr(ui, name, None)
    if callback is None:
        return None
    return callback(*args)


def _resolve_data_file(path: Any, root: Path) -> Path:
    """把校准文件路径解析为绝对路径，并要求位于 <root>/data/ 之内。"""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    data_dir = (root / "data").resolve()
    if resolved == data_dir or data_dir not in resolved.parents:
        raise ValueError(f"校准文件必须位于工作区 data/ 目录内，当前为 {resolved}")
    return resolved


class CalibrationModel:
    """标准缩放 + 多项式特征 + Ridge 的视线回归模型（只存 JSON，不用 pickle）。"""

    def __init__(
        self,
        poly_degree: int = 2,
        ridge_alpha: float = 1.0,
        screen_size: Tuple[int, int] = (1920, 1080),
        ear_baseline: float = 0.3,
        alphas: Optional[Sequence[float]] = None,
        cv_folds: int = 5,
        pose_margin_deg: float = 5.0,
        head_pose_range: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> None:
        self.poly_degree = int(poly_degree)
        self.ridge_alpha = float(ridge_alpha)
        self.alphas: Optional[List[float]] = (
            None if alphas is None else [float(value) for value in alphas]
        )
        self.cv_folds = max(int(cv_folds), 2)
        self.alpha_cv_used = False
        self.screen_size = (int(screen_size[0]), int(screen_size[1]))
        self.ear_baseline = float(ear_baseline)
        self.pose_margin_deg = float(pose_margin_deg)
        self.head_pose_range = _normalize_pose_range(head_pose_range)
        self._pipeline: Optional[Pipeline] = None
        self._samples_x: List[np.ndarray] = []
        self._targets_y: List[Tuple[float, float]] = []
        self._point_ids: List[int] = []
        self._kinds: List[str] = []
        self._mean_error: Optional[float] = None
        self._static_error: Optional[float] = None
        self._head_error: Optional[float] = None

    def _select_alpha(self, x: np.ndarray, y: np.ndarray) -> None:
        """用交叉验证在候选 alpha 中挑选一个（标准化 + 可选多项式 + RidgeCV）。"""
        if not self.alphas:
            return
        if len(self.alphas) == 1:
            self.ridge_alpha = float(self.alphas[0])
            return
        folds = min(self.cv_folds, int(x.shape[0]))
        if folds < 2:
            return
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("poly", PolynomialFeatures(degree=self.poly_degree, include_bias=False)),
                ("ridge", RidgeCV(alphas=np.asarray(self.alphas, dtype=np.float64), cv=folds)),
            ]
        )
        pipeline.fit(x, y)
        self.ridge_alpha = float(pipeline.named_steps["ridge"].alpha_)
        self.alpha_cv_used = True

    def _build_pipeline(self) -> Pipeline:
        """构造一个全新的回归流水线（evaluate 时需要独立副本）。"""
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("poly", PolynomialFeatures(degree=self.poly_degree, include_bias=False)),
                ("ridge", Ridge(alpha=self.ridge_alpha)),
            ]
        )

    def fit(
        self,
        features: Sequence[Sequence[float]],
        targets: Sequence[Sequence[float]],
        point_ids: Optional[Sequence[int]] = None,
        ear_baseline: Optional[float] = None,
        screen_size: Optional[Tuple[int, int]] = None,
        kinds: Optional[Sequence[str]] = None,
        head_pose_range: Optional[Dict[str, Tuple[float, float]]] = None,
        pose_margin_deg: Optional[float] = None,
    ) -> "CalibrationModel":
        """用样本训练模型（静止样本与头动样本合并；可选交叉验证选 alpha）。"""
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(targets, dtype=np.float64)
        if x.ndim != 2:
            raise ValueError("特征必须是二维数组（样本数 x 特征数）")
        if y.shape != (x.shape[0], 2):
            raise ValueError("目标必须是 (样本数, 2) 的屏幕坐标")
        if x.shape[0] < 2:
            raise ValueError("训练样本太少，无法拟合校准模型")
        self._select_alpha(x, y)
        self._pipeline = self._build_pipeline()
        self._pipeline.fit(x, y)
        self._samples_x = [row.copy() for row in x]
        self._targets_y = [(float(row[0]), float(row[1])) for row in y]
        if point_ids is None:
            self._point_ids = [0] * x.shape[0]
        else:
            self._point_ids = [int(value) for value in point_ids]
        if kinds is None:
            self._kinds = [KIND_STATIC] * x.shape[0]
        else:
            self._kinds = [str(value) for value in kinds]
            if len(self._kinds) != x.shape[0]:
                raise ValueError("样本类型 kinds 的长度必须与样本数一致")
        if ear_baseline is not None:
            self.ear_baseline = float(ear_baseline)
        if screen_size is not None:
            self.screen_size = (int(screen_size[0]), int(screen_size[1]))
        if head_pose_range is not None:
            self.head_pose_range = _normalize_pose_range(head_pose_range)
        if pose_margin_deg is not None:
            self.pose_margin_deg = float(pose_margin_deg)
        self._mean_error = None
        self._static_error = None
        self._head_error = None
        return self

    def predict(self, features: Sequence[float]) -> Tuple[float, float]:
        """预测屏幕像素坐标，并裁剪到屏幕范围内。"""
        if self._pipeline is None:
            raise RuntimeError("校准模型尚未训练")
        vector = np.asarray(features, dtype=np.float64).reshape(1, -1)
        prediction = self._pipeline.predict(vector)[0]
        width, height = self.screen_size
        x = float(min(max(prediction[0], 0.0), width - 1))
        y = float(min(max(prediction[1], 0.0), height - 1))
        return x, y

    def _pose_values(self, features: Sequence[float]) -> Optional[Tuple[float, float, float, float]]:
        """从特征向量提取 (yaw, pitch, roll, scale)，角度制。"""
        vector = np.asarray(features, dtype=np.float64).reshape(-1)
        if vector.size <= HEAD_SCALE_INDEX:
            return None
        pose = vector[HEAD_POSE_SLICE] * DEG_PER_UNIT
        scale = float(vector[HEAD_SCALE_INDEX])
        values = (float(pose[0]), float(pose[1]), float(pose[2]), scale)
        if not all(np.isfinite(values)):
            return None
        return values

    def pose_in_range(self, features: Sequence[float]) -> bool:
        """当前头姿是否落在校准范围内（含余量）；未记录范围时恒为 True。"""
        if self.head_pose_range is None:
            return True
        pose = self._pose_values(features)
        if pose is None:
            return True
        for name, value in zip(POSE_FIELDS, pose):
            bounds = self.head_pose_range.get(name)
            if bounds is None:
                continue
            if value < bounds[0] - self.pose_margin_deg or value > bounds[1] + self.pose_margin_deg:
                return False
        return True

    def predict_with_status(self, features: Sequence[float]) -> Tuple[float, float, bool]:
        """预测坐标并返回是否处于已校准的头姿范围内。"""
        x, y = self.predict(features)
        return x, y, self.pose_in_range(features)

    def predict_clamped(
        self,
        features: Sequence[float],
        previous: Optional[Tuple[float, float]],
        max_step: float,
    ) -> Tuple[float, float, bool]:
        """头姿超范围时把本帧位移限幅到 ``max_step`` 像素以内。"""
        x, y, in_range = self.predict_with_status(features)
        if not in_range and previous is not None and max_step and max_step > 0:
            dx = x - float(previous[0])
            dy = y - float(previous[1])
            distance = math.hypot(dx, dy)
            if distance > max_step:
                ratio = float(max_step) / distance
                x = float(previous[0]) + dx * ratio
                y = float(previous[1]) + dy * ratio
        return x, y, in_range

    @property
    def static_error(self) -> Optional[float]:
        """静止样本的平均误差（px），未评估时为 None。"""
        return self._static_error

    @property
    def head_motion_error(self) -> Optional[float]:
        """头动样本的平均误差（px），无头动样本时为 None。"""
        return self._head_error

    @property
    def kinds(self) -> List[str]:
        """训练样本的类型列表（static / head）。"""
        return list(self._kinds)

    @property
    def mean_error(self) -> Optional[float]:
        """最近一次 evaluate() 得到的平均误差（px）。"""
        return self._mean_error

    def evaluate(self) -> float:
        """留一点交叉验证：每次留出一个校准点的全部样本，返回平均误差（px）。

        同时按样本类型记录静止/头动各自的平均误差，供校准质量报告使用。
        """
        if self._pipeline is None or not self._samples_x:
            return 0.0
        x = np.array(self._samples_x, dtype=np.float64)
        y = np.array(self._targets_y, dtype=np.float64)
        ids = np.array(self._point_ids, dtype=np.int64)
        errors: List[float] = []
        static_errors: List[float] = []
        head_errors: List[float] = []
        kinds_by_point = {int(pid): str(kind) for pid, kind in zip(self._point_ids, self._kinds)}
        for point_id in sorted(set(self._point_ids)):
            test_mask = ids == point_id
            train_mask = ~test_mask
            if not test_mask.any() or not train_mask.any():
                continue
            pipeline = self._build_pipeline()
            pipeline.fit(x[train_mask], y[train_mask])
            prediction = pipeline.predict(x[test_mask])
            distances = np.linalg.norm(prediction - y[test_mask], axis=1)
            error = float(np.mean(distances))
            errors.append(error)
            if kinds_by_point.get(int(point_id)) == KIND_HEAD:
                head_errors.append(error)
            else:
                static_errors.append(error)
        self._mean_error = float(np.mean(errors)) if errors else 0.0
        self._static_error = float(np.mean(static_errors)) if static_errors else None
        self._head_error = float(np.mean(head_errors)) if head_errors else None
        return self._mean_error

    def save(self, path: Any, root: Any = None) -> Path:
        """保存为 JSON；覆盖前先把旧文件复制为 .bak.json（不删除旧文件）。"""
        root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
        target = _resolve_data_file(path, root_path)
        if self._pipeline is None:
            raise RuntimeError("校准模型尚未训练，无法保存")
        if target.exists():
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup = target.with_name(f"{target.stem}.{timestamp}.bak.json")
            shutil.copy2(target, backup)
            LOGGER.info("旧校准文件已备份到 %s", backup)
        payload = {
            "version": MODEL_VERSION,
            "screen_width": self.screen_size[0],
            "screen_height": self.screen_size[1],
            "ear_baseline": self.ear_baseline,
            "poly_degree": self.poly_degree,
            "ridge_alpha": self.ridge_alpha,
            "feature_dim": int(len(self._samples_x[0])) if self._samples_x else FEATURE_DIM,
            "features": [[float(value) for value in row] for row in self._samples_x],
            "targets": [[float(value) for value in row] for row in self._targets_y],
            "point_ids": [int(value) for value in self._point_ids],
            "kinds": list(self._kinds),
            "mean_error": self._mean_error,
            "static_mean_error": self._static_error,
            "head_motion_mean_error": self._head_error,
            "pose_margin_deg": self.pose_margin_deg,
            "head_pose_range": _pose_range_to_json(self.head_pose_range),
            "alphas": list(self.alphas) if self.alphas else None,
            "cv_folds": self.cv_folds,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        LOGGER.info("校准模型已保存到绝对路径 %s", target)
        return target

    @classmethod
    def load(
        cls,
        path: Any,
        expected_screen: Optional[Tuple[int, int]] = None,
        root: Any = None,
    ) -> "CalibrationModel":
        """从 JSON 载入并重新 fit；屏幕分辨率不一致时抛 ScreenSizeMismatchError。"""
        root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
        target = _resolve_data_file(path, root_path)
        if not target.is_file():
            raise FileNotFoundError(f"校准文件不存在：{target}")
        with open(target, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        version = int(payload.get("version", 0))
        if version != MODEL_VERSION:
            raise ModelVersionMismatchError(
                f"校准模型版本 {version} 与当前版本 {MODEL_VERSION} 不兼容，请重新校准"
            )
        screen = (int(payload["screen_width"]), int(payload["screen_height"]))
        if expected_screen is not None:
            expected = (int(expected_screen[0]), int(expected_screen[1]))
            if expected != screen:
                raise ScreenSizeMismatchError(
                    f"校准文件屏幕尺寸 {screen} 与当前屏幕 {expected} 不一致，请重新校准"
                )
        pose_range = _normalize_pose_range(payload.get("head_pose_range"))
        margin = float(payload.get("pose_margin_deg", 5.0))
        model = cls(
            poly_degree=payload.get("poly_degree", 2),
            ridge_alpha=payload.get("ridge_alpha", 1.0),
            screen_size=screen,
            ear_baseline=payload.get("ear_baseline", 0.3),
            alphas=payload.get("alphas"),
            cv_folds=payload.get("cv_folds", 5),
            pose_margin_deg=margin,
            head_pose_range=pose_range,
        )
        model.fit(
            payload["features"],
            payload["targets"],
            point_ids=payload.get("point_ids"),
            ear_baseline=payload.get("ear_baseline", 0.3),
            screen_size=screen,
            kinds=payload.get("kinds"),
            head_pose_range=pose_range,
            pose_margin_deg=margin,
        )
        model._mean_error = payload.get("mean_error")
        model._static_error = payload.get("static_mean_error")
        model._head_error = payload.get("head_motion_mean_error")
        LOGGER.info("已从 %s 载入校准模型（重新 fit 完成）", target)
        return model


class Calibrator:
    """执行完整校准：初始基线 -> 9 点静止采样 -> 头动补偿采样 -> 眨眼练习。"""

    def __init__(
        self,
        cfg: AppConfig,
        profile: Optional[FaceProfile] = None,
    ) -> None:
        self.cfg = cfg
        self.profile = profile
        self.created_profile: Optional[FaceProfile] = None
        self.head_estimator = HeadPoseEstimator(
            profile=profile,
            focal_scale=cfg.face_profile.focal_scale,
            reprojection_error_px=cfg.face_profile.reprojection_error_px,
            smoothing_alpha=cfg.face_profile.smoothing_alpha,
        )

    def set_profile(self, profile: Optional[FaceProfile]) -> None:
        """设置个人面部模板并同步头姿估计器。"""
        self.profile = profile
        self.head_estimator.set_profile(profile)

    def calibrate_face(self, camera: Any, detector: Any, ui: Any) -> Optional[FaceProfile]:
        """执行面部标定并记录结果；ESC 取消返回 None。"""
        profiler = FaceProfiler(self.cfg.face_profile)
        profile = profiler.run(camera, detector, ui)
        if profile is not None:
            self.set_profile(profile)
            self.created_profile = profile
        return profile

    def _feature_vector(self, face: Any) -> Optional[np.ndarray]:
        """用带平滑/初值的头姿估计器构造特征向量，保证采样与运行时一致。"""
        pose = self.head_estimator.estimate(face)
        return build_feature_vector(
            face,
            pose=pose,
            profile=self.profile,
            eyeball_offset=self.cfg.face_profile.eyeball_offset,
        )

    # ---------------- 几何 ----------------
    def grid_points(self, screen_width: int, screen_height: int) -> List[Tuple[float, float]]:
        """按 grid 与 margin 生成 3x3（或 NxN）校准点，行优先。"""
        grid = max(int(self.cfg.calibration.grid), 2)
        margin = float(self.cfg.calibration.margin)
        span_x = screen_width * (1.0 - 2.0 * margin)
        span_y = screen_height * (1.0 - 2.0 * margin)
        xs = [screen_width * margin + span_x * index / (grid - 1) for index in range(grid)]
        ys = [screen_height * margin + span_y * index / (grid - 1) for index in range(grid)]
        return [(x, y) for y in ys for x in xs]

    def head_motion_points(self, screen_width: int, screen_height: int) -> List[Tuple[float, float]]:
        """头动校准注视点：中心 + 四角附近，数量由配置限制在 1..5。"""
        margin = float(self.cfg.calibration.margin)
        left = screen_width * margin
        right = screen_width * (1.0 - margin)
        top = screen_height * margin
        bottom = screen_height * (1.0 - margin)
        candidates = [
            (screen_width * 0.5, screen_height * 0.5),
            (left, top),
            (right, top),
            (left, bottom),
            (right, bottom),
        ]
        count = min(max(int(self.cfg.head_motion.points), 1), len(candidates))
        return candidates[:count]

    @staticmethod
    def head_pose_range_from_features(features: Any) -> Optional[Dict[str, Tuple[float, float]]]:
        """由头动样本计算 yaw/pitch/roll/scale 的观测范围。"""
        values = np.asarray(features, dtype=np.float64)
        if values.ndim != 2 or values.shape[0] == 0:
            return None
        columns = {
            "yaw": values[:, 6] * DEG_PER_UNIT,
            "pitch": values[:, 7] * DEG_PER_UNIT,
            "roll": values[:, 8] * DEG_PER_UNIT,
            "scale": values[:, HEAD_SCALE_INDEX],
        }
        result: Dict[str, Tuple[float, float]] = {}
        for name, column in columns.items():
            finite = column[np.isfinite(column)]
            if finite.size:
                result[name] = (float(np.min(finite)), float(np.max(finite)))
        return result or None

    def _pose_within_limits(self, vector: np.ndarray) -> bool:
        """采样时头姿是否在配置的合理范围内（用于丢弃异常帧）。"""
        cfg = self.cfg.head_motion
        yaw = float(vector[HEAD_POSE_SLICE][0]) * DEG_PER_UNIT
        pitch = float(vector[HEAD_POSE_SLICE][1]) * DEG_PER_UNIT
        roll = float(vector[HEAD_POSE_SLICE][2]) * DEG_PER_UNIT
        if not all(np.isfinite([yaw, pitch, roll])):
            return False
        return (
            abs(yaw) <= cfg.max_yaw_deg
            and abs(pitch) <= cfg.max_pitch_deg
            and abs(roll) <= cfg.max_roll_deg
        )

    # ---------------- 采集辅助 ----------------
    def _check_esc(self, ui: Any) -> None:
        if _call_ui(ui, "pump", 1) == ESC_KEY:
            raise CalibrationCancelled("用户按 ESC 取消了校准")

    def _collect_ears(
        self,
        camera: Any,
        detector: Any,
        ui: Any,
        duration: float,
        ears: List[float],
        prompt: str,
    ) -> None:
        """在 duration 秒内持续采集平均 EAR，写入 ears。"""
        _call_ui(ui, "show_text", prompt)
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            frame = camera.read()
            if frame is not None:
                face = detector.detect(frame)
                if face is not None:
                    ear_a, ear_b = compute_ear(face)
                    value = (ear_a + ear_b) / 2.0
                    if np.isfinite(value):
                        ears.append(float(value))
            self._check_esc(ui)

    def _initial_baseline(self, camera: Any, detector: Any, ui: Any) -> Tuple[float, List[float]]:
        """收集初始睁眼基线（80 分位数），有效帧不足则重试一次。"""
        for attempt in range(2):
            ears: List[float] = []
            self._collect_ears(
                camera, detector, ui, BASELINE_SECONDS, ears, "Look at the screen, keep eyes open"
            )
            if len(ears) >= MIN_VALID_FRAMES:
                return float(np.percentile(ears, 80)), ears
            LOGGER.warning("初始基线有效帧不足（%d/%d），重试", len(ears), MIN_VALID_FRAMES)
        raise RuntimeError("无法收集到足够的睁眼基线样本，请检查摄像头与光线后重试（可按 ESC 取消）")

    def _sample_points(
        self,
        camera: Any,
        detector: Any,
        ui: Any,
        points: Sequence[Tuple[float, float]],
        initial_baseline: float,
        all_ears: List[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """逐点显示、采样并收集特征；每点至少 10 个有效样本，否则重采一次。"""
        features: List[np.ndarray] = []
        targets: List[Tuple[float, float]] = []
        point_ids: List[int] = []
        total = len(points)
        settle = float(self.cfg.calibration.settle_time)
        sample = float(self.cfg.calibration.sample_time)
        for index, (point_x, point_y) in enumerate(points):
            collected: List[np.ndarray] = []
            for attempt in range(2):
                collected = []
                _call_ui(ui, "show_progress", index + 1, total)
                settle_start = time.perf_counter()
                while time.perf_counter() - settle_start < settle:
                    elapsed = time.perf_counter() - settle_start
                    shrink = max(0.0, 1.0 - elapsed / settle) if settle > 0 else 0.0
                    _call_ui(ui, "draw_target", point_x, point_y, shrink)
                    self._check_esc(ui)
                sample_start = time.perf_counter()
                while time.perf_counter() - sample_start < sample:
                    frame = camera.read()
                    _call_ui(ui, "draw_target", point_x, point_y, 0.0)
                    if frame is not None:
                        face = detector.detect(frame)
                        if face is not None:
                            ear_a, ear_b = compute_ear(face)
                            mean_ear = (ear_a + ear_b) / 2.0
                            if np.isfinite(mean_ear):
                                all_ears.append(float(mean_ear))
                                if mean_ear > initial_baseline * 0.7:
                                    vector = self._feature_vector(face)
                                    if vector is not None:
                                        collected.append(vector)
                    self._check_esc(ui)
                if len(collected) >= MIN_POINT_SAMPLES:
                    break
                LOGGER.warning("校准点 %d 有效样本不足（%d），重采一次", index + 1, len(collected))
            if len(collected) < MIN_POINT_SAMPLES:
                raise RuntimeError(
                    f"校准点 {index + 1} 有效样本不足，请重试（可按 ESC 取消）"
                )
            features.extend(collected)
            targets.extend([(float(point_x), float(point_y))] * len(collected))
            point_ids.extend([index] * len(collected))
        return (
            np.asarray(features, dtype=np.float64),
            np.asarray(targets, dtype=np.float64),
            np.asarray(point_ids, dtype=np.int64),
        )

    def _sample_head_motion(
        self,
        camera: Any,
        detector: Any,
        ui: Any,
        points: Sequence[Tuple[float, float]],
        initial_baseline: float,
        all_ears: List[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """头动阶段：盯住固定点，缓慢上下左右转头并画小圈；异常帧丢弃。"""
        cfg = self.cfg.head_motion
        features: List[np.ndarray] = []
        targets: List[Tuple[float, float]] = []
        point_ids: List[int] = []
        total = len(points)
        duration = float(cfg.per_point_seconds)
        settle = float(cfg.settle_time)
        prompt = "Keep eyes on the dot; slowly turn your head up/down/left/right"
        for index, (point_x, point_y) in enumerate(points):
            collected: List[np.ndarray] = []
            for attempt in range(2):
                collected = []
                settle_start = time.perf_counter()
                while time.perf_counter() - settle_start < settle:
                    _call_ui(ui, "show_head_motion", index + 1, total, duration, prompt)
                    _call_ui(ui, "draw_target", point_x, point_y, 0.0)
                    self._check_esc(ui)
                start = time.perf_counter()
                while True:
                    elapsed = time.perf_counter() - start
                    if elapsed >= duration:
                        break
                    frame = camera.read()
                    _call_ui(
                        ui,
                        "show_head_motion",
                        index + 1,
                        total,
                        max(0.0, duration - elapsed),
                        prompt,
                    )
                    _call_ui(ui, "draw_target", point_x, point_y, 0.0)
                    if frame is not None:
                        face = detector.detect(frame)
                        if face is not None:
                            ear_a, ear_b = compute_ear(face)
                            mean_ear = (ear_a + ear_b) / 2.0
                            if np.isfinite(mean_ear):
                                all_ears.append(float(mean_ear))
                                if mean_ear > initial_baseline * 0.7:
                                    vector = self._feature_vector(face)
                                    if vector is not None and self._pose_within_limits(vector):
                                        collected.append(vector)
                    self._check_esc(ui)
                if len(collected) >= MIN_HEAD_POINT_SAMPLES:
                    break
                LOGGER.warning(
                    "头动点 %d 有效样本不足（%d/%d），重采一次",
                    index + 1,
                    len(collected),
                    MIN_HEAD_POINT_SAMPLES,
                )
            if not collected:
                LOGGER.warning("头动点 %d 无有效样本，跳过", index + 1)
                continue
            features.extend(collected)
            targets.extend([(float(point_x), float(point_y))] * len(collected))
            point_ids.extend([HEAD_MOTION_POINT_ID_OFFSET + index] * len(collected))
        if not features:
            return (
                np.zeros((0, FEATURE_DIM), dtype=np.float64),
                np.zeros((0, 2), dtype=np.float64),
                np.zeros((0,), dtype=np.int64),
            )
        return (
            np.asarray(features, dtype=np.float64),
            np.asarray(targets, dtype=np.float64),
            np.asarray(point_ids, dtype=np.int64),
        )

    def _blink_practice(
        self,
        camera: Any,
        detector: Any,
        ui: Any,
        final_baseline: float,
    ) -> None:
        """眨眼练习：依次提示 2/3/4 次，只显示识别结果，不触发真实动作。"""
        practice = ClickDetector(self.cfg.click)
        practice.set_mode("blink_sequence")
        for target_count in (2, 3, 4):
            action = self.cfg.click.actions.get(target_count, "none")
            practice.reset()
            deadline = time.perf_counter() + PRACTICE_TIMEOUT
            while time.perf_counter() < deadline:
                frame = camera.read()
                _call_ui(
                    ui,
                    "show_blink_practice",
                    target_count,
                    practice.pending_count(),
                    action,
                )
                if frame is not None:
                    face = detector.detect(frame)
                    if face is None:
                        practice.update(time.perf_counter(), 0.0, final_baseline, (0.0, 0.0), False)
                    else:
                        ear_a, ear_b = compute_ear(face)
                        mean_ear = (ear_a + ear_b) / 2.0
                        event = practice.update(
                            time.perf_counter(), mean_ear, final_baseline, (0.0, 0.0), True
                        )
                        if event is not None and event.blink_count >= target_count:
                            break
                if _call_ui(ui, "pump", 1) == ESC_KEY:
                    return

    # ---------------- 主流程 ----------------
    def run(self, camera: Any, detector: Any, ui: Any, screen_size: Tuple[int, int]) -> CalibrationModel:
        """执行完整校准并返回训练好的模型。"""
        LOGGER.info("开始校准：先收集初始睁眼基线")
        if self.profile is None and self.cfg.face_profile.enabled:
            LOGGER.info("未检测到个人面部模板，先进入面部标定阶段")
            profile = self.calibrate_face(camera, detector, ui)
            if profile is None:
                raise CalibrationCancelled("用户取消了面部标定")
        initial_baseline, initial_ears = self._initial_baseline(camera, detector, ui)
        all_ears: List[float] = list(initial_ears)
        points = self.grid_points(int(screen_size[0]), int(screen_size[1]))
        features, targets, point_ids = self._sample_points(
            camera, detector, ui, points, initial_baseline, all_ears
        )
        kinds = [KIND_STATIC] * int(features.shape[0])
        head_pose_range: Optional[Dict[str, Tuple[float, float]]] = None
        if self.cfg.head_motion.enabled:
            _call_ui(
                ui,
                "show_text",
                "Head-motion calibration: follow the dot and slowly turn your head",
            )
            head_points = self.head_motion_points(int(screen_size[0]), int(screen_size[1]))
            head_features, head_targets, head_ids = self._sample_head_motion(
                camera, detector, ui, head_points, initial_baseline, all_ears
            )
            if head_features.shape[0] > 0:
                features = np.vstack([features, head_features])
                targets = np.concatenate([targets, head_targets], axis=0)
                point_ids = np.concatenate([point_ids, head_ids], axis=0)
                kinds.extend([KIND_HEAD] * int(head_features.shape[0]))
                head_pose_range = self.head_pose_range_from_features(head_features)
                LOGGER.info(
                    "头动校准采集有效样本 %d 个，头姿范围 %s",
                    int(head_features.shape[0]),
                    head_pose_range,
                )
            else:
                LOGGER.warning("头动校准未采集到有效样本，改用静止样本训练")
        final_baseline = float(np.percentile(all_ears, 80)) if all_ears else initial_baseline
        model = CalibrationModel(
            poly_degree=self.cfg.calibration.poly_degree,
            ridge_alpha=self.cfg.calibration.ridge_alpha,
            screen_size=screen_size,
            ear_baseline=final_baseline,
            alphas=self.cfg.head_motion.ridge_alphas,
            cv_folds=self.cfg.head_motion.cv_folds,
            pose_margin_deg=self.cfg.head_motion.pose_margin_deg,
            head_pose_range=head_pose_range,
        )
        model.fit(
            features,
            targets,
            point_ids=point_ids,
            ear_baseline=final_baseline,
            screen_size=screen_size,
            kinds=kinds,
            head_pose_range=head_pose_range,
            pose_margin_deg=self.cfg.head_motion.pose_margin_deg,
        )
        error = model.evaluate()
        LOGGER.info(
            "校准完成：平均误差 %.1f px（静止 %s px，头动 %s px；初始基线 %.3f，"
            "最终基线 %.3f；alpha=%.3g）",
            error,
            f"{model.static_error:.1f}" if model.static_error is not None else "无",
            f"{model.head_motion_error:.1f}" if model.head_motion_error is not None else "无",
            initial_baseline,
            final_baseline,
            model.ridge_alpha,
        )
        if error > 250.0:
            LOGGER.warning("校准质量较差，建议重新校准（保持头部稳定、光线充足）")
            _call_ui(ui, "show_text", "Poor calibration quality, consider recalibrating")
        if self.cfg.calibration.practice_blinks:
            self._blink_practice(camera, detector, ui, final_baseline)
        return model
