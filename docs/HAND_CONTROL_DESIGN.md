# 右手控制光标移动 —— 设计说明

## 1. 目标与范围

- 新增「右手食指/手掌控制光标移动」功能，**眼控与头控全部保留**。
- 眼球/眨眼仍负责点击：连续眨眼、双击、右键、拖拽逻辑完全不变。
- 手只负责「移动光标」，不负责点击（点击交给眼睛）。
- 默认 `hand_control.pointer_source = "hand"`，即启动后用手控移动、用眼睛点击。
- 通过 `--pointer-source` 可在 `eye / hand / hybrid` 之间切换。

## 2. 总体数据流

```
摄像头帧(镜像)
   │
   ├─ FaceMesh ──> 眨眼(EAR) ──> ClickDetector ──> 点击动作        （始终运行）
   │            └─ 头姿/特征 ──> 眼控或头控光标                     （按 pointer_source）
   │
   └─ Hands ────> 21 关键点 ──> is_open_palm ──> OpenPalmGate
                                                    │ open
                                                    ▼
                                          HandPointer ──> 光标坐标
```

判定优先级（每帧）：

| pointer_source | gate 打开 | gate 关闭 |
|---|---|---|
| `eye`（原行为，F5 可在 eye/head 间切） | 眼/头控光标 | 眼/头控光标 |
| `hand` | **手控光标** | **光标不动**（眼/头仍运行但不移动光标） |
| `hybrid` | **手控光标** | 眼/头控光标 |

> 无论哪种模式，眨眼检测、头姿估计、特征计算都继续运行，仅"是否移动光标"不同。

## 3. 模块划分

### 3.1 `eyemouse/hand_tracker.py`

- 封装 `mediapipe.solutions.hands.Hands(max_num_hands=2, model_complexity=0)`，与 FaceMesh 共用同一帧（各自 `process` RGB 拷贝）。
- `mirror_handedness`：是否把 MediaPipe 的 `Left/Right` 互换。本工程摄像头帧默认已左右镜像（`camera.mirror=true`），此时 MediaPipe 按自拍视角输出的标签即为真实左右手，故默认 `false`；若 `camera.mirror=false`（非镜像输入），再置 `true`。
- 只接受**右手**（`want="Right"`），返回：

  ```python
  @dataclass
  class HandLandmarks:
      pts_px: np.ndarray   # (21, 2) 摄像头帧像素坐标
      pts_norm: np.ndarray # (21, 2) 归一化坐标
      handedness: str      # 校正后的 "Left"/"Right"
      score: float         # handedness 置信度
      img_w: int
      img_h: int
  ```

- 未检出目标手时返回 `None`。

### 3.2 `eyemouse/hand_gesture.py`（纯函数 + 状态机，便于合成测试）

- `is_open_palm(points, open_ratio, finger_spread_min) -> bool`
  1. 四指：`|tip − wrist| > |PIP − wrist| × open_ratio`（食指 6/8、中指 10/12、无名指 14/16、小指 18/20）。
  2. 拇指：`|tip4 − MCP17| > |IP3 − MCP17| × open_ratio`。
  3. 并拢检查：相邻指尖距离（8-12、12-16、16-20）除以掌宽 `|MCP5 − MCP17|`，最小值须 ≥ `finger_spread_min`。
  4. 全部为**距离比较**，因此对整手旋转（90°/180°）天然不变。
- `OpenPalmGate(enter_frames, exit_frames, lost_timeout)`
  - 连续 `enter_frames` 帧满足才进入 OPEN；连续 `exit_frames` 帧不满足才退出 CLOSED。
  - 手完全丢失超过 `lost_timeout` 秒立即退出。
  - `update(now, hand_present, palm_open)` 返回当前是否 OPEN；`reset()` 清状态。

### 3.3 `eyemouse/hand_pointer.py`

- 追踪点 = `mean(wrist0, MCP5, MCP9, MCP13, MCP17)`（手掌中心），归一化到 `[0,1]²`。
- `mapping="relative"`（默认）：gate 进入时记录锚点 `anchor`（手位置）与参考 `ref`（当前光标位置），
  `target = ref + (point − anchor) × gain × screen_size`；退出即失效 -> 不会跳变。
- `mapping="absolute"`：把手在画面中的位置线性映射到屏幕，只取中间 `active_region`（默认 0.6）为满量程，
  `ratio = clamp((point − 0.5) / (active_region/2), −1, 1) × gain`。
- 拥有**独立** `OneEuroFilter2D(min_cutoff, beta, d_cutoff=1.0)` 与死区 `deadzone_px`，
  与眼控滤波器完全隔离；死区内保持上一次输出。

## 4. app.py 集成要点

- `hand_tracker` 仅在 `pointer_source ∈ {hand, hybrid}` 且 `hand_control.enabled` 时创建；创建失败降级为眼控。
- `hand_every_n_frames`：每 N 帧才跑一次 Hands，其余帧复用上次结果（省 CPU）。
- gate 上升沿调用 `hand_pointer.activate(point, last_mouse)`；下降沿 `deactivate()`。
- `F9` 暂停 / `F10` 退出保持不变；暂停、重校准、切换来源时 `reset()` 手部状态。
- `suspend_blink_while_hand=true` 时，gate 打开期间暂停眨眼点击（避免挥手误触），默认 false。
- 眼控路径拆出 `move_cursor` 开关：hand 模式下仍计算特征/预测，但不调用 `mouse.move`。

## 5. 配置（`config.yaml` → `hand_control`）

| 键 | 默认 | 说明 |
|---|---|---|
| `enabled` | true | 是否启用手控模块 |
| `pointer_source` | "hand" | eye / hand / hybrid |
| `mirror_handedness` | false | 是否互换左右手标签；`camera.mirror=true` 时保持 false |
| `open_ratio` | 1.1 | 张开判定比例（指尖/指节到手腕距离） |
| `finger_spread_min` | 0.25 | 相邻指尖最小间距（相对掌宽） |
| `enter_frames` | 5 | 连续满足进入 OPEN 的帧数 |
| `exit_frames` | 5 | 连续不满足退出 OPEN 的帧数 |
| `lost_timeout` | 0.3 | 手丢失多久立即退出（秒） |
| `mapping` | "relative" | relative / absolute |
| `gain` | 2.4 | 手位移 → 光标位移增益 |
| `tracking_point` | thumb_tip | 光标基准点：thumb_tip 拇指指尖（默认）/ palm 手掌中心 / wrist 手腕 / index_tip 食指指尖 |
| `require_thumb` | true | 「张开手掌」判定是否必须拇指伸出；false 时只看四指 |
| `active_region` | 0.6 | absolute 模式的满量程区域（画面比例） |
| `min_cutoff` | 0.8 | 手部 One Euro min_cutoff |
| `beta` | 0.01 | 手部 One Euro beta |
| `deadzone_px` | 12.0 | 手控死区（像素） |
| `hand_every_n_frames` | 1 | 每 N 帧检测一次手 |
| `suspend_blink_while_hand` | false | gate 打开时暂停眨眼点击 |

## 6. 调试叠加层

- 手部 21 点与骨架（`map_point_to_canvas` 映射，沿用摄像头帧实际 `(w,h)`）。
- `Hand: OPEN/CLOSED`、`Src: eye/hand/hybrid`、`HandFPS`。

## 7. 测试（合成 21 关键点，不开摄像头）

- 张开手为真；握拳 / 只伸食指 / 四指并拢 / 拇指收起 为假。
- 整手旋转 90°/180° 判定不变。
- `OpenPalmGate` 进入/退出滞回与丢失超时。
- relative 映射位移正确；gate 重新进入无跳变。
- hand 模式下 gate 关闭不移动光标；眨眼点击仍触发。
- 配置校验。

## 8. 已知限制

- 左右手标签取决于 `camera.mirror` 与 `mirror_handedness` 是否匹配，两者配错会把左右手判反。
- 光照不足、手部遮挡面部会影响 FaceMesh（眨眼检测）与手部同时检测。
- `model_complexity=0` + 每帧 Hands 会增加 CPU 占用，可用 `hand_every_n_frames` 降频。
- 手控只移动光标，不产生点击；点击始终由眼睛负责。