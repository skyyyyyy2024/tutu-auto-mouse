# 个人面部标定与几何视线估计 —— 设计说明

## 1. 目标

在原有「9 点屏幕校准 + 头动补偿」的基础上，引入**个人面部几何模板**，让头部姿态
（PnP）与视线角度估计贴合使用者本人的面部尺寸，并在特征层加入几何视线角度
（`gaze_yaw` / `gaze_pitch`），提高头动时的稳定性。

关键设计原则：

- **只做相对估计**：MediaPipe FaceMesh 的 `z` 是相对深度（以图像宽度为单位的近似值），
  不是毫米级真值。所有输出只用于相对补偿，不宣称绝对物理准确。
- **个性化模板可回退**：没有个人模板时，自动使用通用模板，功能不退化。
- **旧模型安全降级**：特征维度/模型版本变化时，旧校准文件只提示重新校准，不崩溃。
- **可测试**：核心几何全部用合成 3D 点 + 已知旋转验证。

## 2. 数据：稳定点集（约 20 个）

在 `eyemouse/landmarks.py` 新增 `STABLE_POINT_INDEXES`（20 个 MediaPipe 索引）：

| 区域 | 索引 |
| --- | --- |
| 额头 | 10, 151 |
| 眉间/鼻梁 | 9, 8, 168, 6, 197, 195 |
| 鼻尖/鼻翼 | 1, 4, 129, 358 |
| 眼角 | 33, 133, 263, 362 |
| 嘴角 | 61, 291 |
| 下巴/上唇 | 152, 199 |

这些点在自然表情下相对刚体，适合作为模板锚点。尺度参考取**两外眼角**（33 与 263）
之间的 3D 距离。

### 坐标统一

MediaPipe 的 `pts_3d` 是 `(x/width, y/height, z/width)` 各向异性地归一化。为得到各向同性
坐标，先还原为像素尺度：

```text
X = x * width,  Y = y * height,  Z = z * width
```

再按两外眼角距离归一化：`template = metric / eye_corner_distance`。这样模板无量纲，
`solvePnP` 求得的旋转不受尺度影响（旋转与模型尺度无关），平移量仅用于重投影误差，
不需要物理量纲。

## 3. 个人模板采集（`eyemouse/face_profile.py`）

- 提示：正对镜头、中性表情；持续采集，丢弃无脸帧与非有限值帧。
- 目标有效帧数默认 **150**（`face_profile.samples`）。
- 对选定的 20 个稳定点，逐点取**中位数**（对眨眼/局部抖动鲁棒）得到 3D 模板。
- 质量指标：
  - `sample_frames`：有效帧数；
  - `point_std`：逐点跨帧标准差的中位数（相对尺度），越小越稳；
  - `scale_reference`：两外眼角距离（像素，采集时的中位数），用于诊断。
- 保存到 `data/face_profile.json`，字段：`version`、`point_indexes`、`points_3d`、
  `sample_frames`、`quality`、`created`。覆盖前先写 `.bak.json` 备份。

## 4. 头姿估计升级（`eyemouse/head_pose.py`）

- 有个人模板用个人模板，否则回退通用 `MODEL_POINTS`。
- `solvePnP` 使用上一帧 `rvec/tvec` 作为初值（`useExtrinsicGuess=True`），失败时退回无初值。
- 对 `yaw/pitch/roll` 做时间 EMA 平滑；角度按最短弧差处理 **±180° 回绕**
  （`wrap_angle_delta`）。
- 焦距默认取图像宽度，可由 `face_profile.focal_scale` 覆盖（`focal = width * scale`）。
- 输出重投影误差（`cv2.projectPoints` 后与图像点求 RMS）；超过
  `face_profile.reprojection_error_px` 时标记该帧 `trustworthy=False`。

对外同时保留无状态的向后兼容函数 `estimate_head_pose(face)`；新增有状态类
`HeadPoseEstimator`（含 `estimate()` / `reset()`）。

## 5. 几何视线（`eyemouse/gaze_geometry.py`）

- 左右眼球中心：取该眼**眼角中点**（A: 33-133，B: 263-362）沿头坐标系 `-z`
  方向后移 `eyeball_offset * scale`（`face_profile.eyeball_offset`，默认 0.5）。
- 视线方向：虹膜中心 3D 坐标减去眼球中心，归一化后在头坐标系下求角度：
  - `gaze_yaw = atan2(dx, dz)`，`gaze_pitch = atan2(dy, dz)`（度）。
- 双眼平均，越界或非有限时回退 0。
- 输入为头坐标系下的模板/关键点；头部旋转只影响模板与图像的对应关系，头坐标系角度
  即「眼在头内」角度，供回归模型使用。

## 6. 特征与模型版本（`eyemouse/features.py`、`eyemouse/calibration.py`）

- 特征向量 `12 -> 14` 维，新增 `gaze_yaw/DEG_PER_UNIT`、`gaze_pitch/DEG_PER_UNIT`
  （索引 12、13）；`FEATURE_DIM = 14`；新增 `GAZE_SLICE = slice(12, 14)`。
- 旧的头姿三元组、鼻尖平移、头部尺度索引保持稳定，便于增量迁移。
- `calibration.MODEL_VERSION` 由 `2` 升到 `3`。`CalibrationModel.load` 遇到
  版本不匹配抛 `ModelVersionMismatchError`（`ValueError` 子类），应用层按“重新校准”
  处理并给出中文提示，**不崩溃**。

## 7. 校准流程

- 启动时若 `face_profile.enabled` 且 `data/face_profile.json` 不存在/无效：
  先进入**面部标定阶段**（约 150 帧），再进入原有屏幕校准。
- 新增 `--recalibrate-face`：只重做面部标定；若此后仍无屏幕校准模型，再走完整校准。
- 面部标定同样支持 ESC 取消，走 `CalibrationCancelled`。

## 8. 调试叠加层（`eyemouse/ui.py`）

- 显示 `yaw/pitch/roll`、`gaze_yaw/gaze_pitch`、重投影误差。
- 用 `cv2.projectPoints` 把 3D 坐标轴投影到帧，再经 `map_point_to_canvas`
  映射到 480x360 画布，画头部朝向轴线（红/绿/蓝三轴）。
- 叠加层坐标映射继续复用 `map_point_to_canvas`，不使用屏幕坐标。

## 9. 配置项（`config.yaml` -> `face_profile`）

```yaml
face_profile:
  enabled: true                 # 是否启用个人面部标定
  samples: 150                  # 目标有效帧数
  eyeball_offset: 0.5           # 眼球中心沿 -z 后移比例（相对两外眼角距离）
  focal_scale: 1.0              # 焦距 = 图像宽度 * focal_scale
  reprojection_error_px: 8.0    # 重投影误差阈值，超过标记不可信
  smoothing_alpha: 0.6          # 头姿角度 EMA 系数（1=不平滑）
  file: "data/face_profile.json"
```

## 10. 测试与限制

测试（合成数据，不开摄像头）：

1. 已知旋转生成 3D->2D 投影，`solvePnP` 恢复角度误差 < 1°。
2. 比例失配时，个人模板的重投影误差小于通用模板。
3. 角度 ±180° 回绕平滑正确。
4. 旧版本校准文件加载抛 `ModelVersionMismatchError`，应用层不崩溃。
5. 面部模板采集/保存/加载/备份、质量指标。
6. 几何视线：虹膜居中 -> 角度约 0；偏移 -> 角度方向正确。
7. `FEATURE_DIM == 14` 且特征有限。

限制：

- `z` 深度是**相对估计**，绝对精度有限；眼球中心后移量与焦距均为经验参数。
- 个人模板只做相对冻结，长时间不变的表情/体重变化可能需要重新标定。
- 单人单脸假设；多人场景取第一张脸。