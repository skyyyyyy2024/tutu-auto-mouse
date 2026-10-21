# EyeMouse 项目状态报告

> 生成时间：2026-10-06 ｜ 代码基线：地址表 `docs/change_manifest.json` 第 **374** 条 ｜ 测试：**179 passed**
> 本文面向开发者/维护者，说明「现在有什么功能」以及「接手时必须知道的事」。

---

## 1. 项目是什么

用普通 RGB 摄像头（无需红外）控制鼠标，全部处理在本地完成：

- **光标移动**：默认由**右手**控制（大拇指指尖为基准点）；也可切换为**眼睛注视**或**面部朝向**。
- **点击**：**始终由眼睛负责** —— 连续眨眼 2/3/4/5 次触发单击 / 右键 / 双击 / 拖拽。
- **隐私**：不上传、不保存任何摄像头图像，只保存校准得到的数值特征。

---

## 2. 运行环境（重要偏离）

| 项 | 实际值 | 说明 |
|---|---|---|
| Python | **3.12.8** | 任务书要求 3.10/3.11；本机无这两个版本，且 `mediapipe==0.10.14` 官方提供 `cp312` wheel，已实测可用，故采用 3.12.8 并记录此偏离 |
| 解释器 | `.venv\Scripts\python.exe` | 所有命令/子进程统一用它，**不要用全局 python** |
| mediapipe | 0.10.14 | FaceMesh（人脸 478 点 + 虹膜）与 Hands（21 点） |
| opencv | **4.11.0** | `requirements.txt` pin 的是 `opencv-python==4.9.0.80`，但 mediapipe 会附带安装 `opencv-contrib-python`，运行时实际是 4.11.0 |
| numpy | 1.26.4 | requirements 约束 `<2` |
| scikit-learn | 1.9.1 | 校准回归（Ridge + 交叉验证） |

子进程环境变量约定：`TEMP` / `TMP` / `TMPDIR` 一律设为 `<工作区>\.tmp`，避免写入系统临时目录。

---

## 3. 启动命令

工作目录：`D:\TEST\eye_MOUSE`

| 命令 | 作用 |
|---|---|
| `.\.venv\Scripts\python.exe main.py` | **默认启动（手控）** |
| `.\.venv\Scripts\python.exe main.py --pointer-source eye` | 眼控（眼睛看哪光标到哪） |
| `.\.venv\Scripts\python.exe main.py --pointer-source hand` | 手控（等同默认） |
| `.\.venv\Scripts\python.exe main.py --pointer-source hybrid` | 混合：手掌张开由手接管，否则回眼控/头控 |
| `.\.venv\Scripts\python.exe main.py --hand-test` | 手部自检：只看右手 21 点与 Gate 状态，**不动鼠标** |
| `.\.venv\Scripts\python.exe main.py --camera-test` | 摄像头自检：看人脸关键点 |
| `.\.venv\Scripts\python.exe main.py --dry-run` | 不真正控制鼠标，只打印动作 |
| `.\.venv\Scripts\python.exe main.py --recalibrate` | 忽略已有校准，强制全部重做 |
| `.\.venv\Scripts\python.exe main.py --recalibrate-face` | 只重做个人面部标定 |
| `.\.venv\Scripts\python.exe main.py --no-window` | 不显示调试窗口 |
| `.\.venv\Scripts\python.exe main.py --log-level DEBUG` | 覆盖日志级别 |
| `.\.venv\Scripts\python.exe main.py --config PATH` | 指定配置文件 |

启动时会打印热键说明；若 `data/calibration.json` 不存在或版本/分辨率不匹配，会先进入校准流程。

---

## 4. 光标来源：手控（默认）

- **触发（gate）**：连续 `enter_frames=5` 帧判定「张开手掌」→ OPEN；连续 `exit_frames=5` 帧不满足 → CLOSED；手消失超过 `lost_timeout=0.3s` 立即 CLOSED。
- **「张开手掌」判定**：四指（指尖到手腕距离 > PIP 到手腕距离 × `open_ratio`）+ 拇指（拇指尖到小指 MCP > 拇指 IP 到小指 MCP × `open_ratio`）+ 相邻指尖间距/掌宽 ≥ `finger_spread_min`。`require_thumb=false` 可去掉拇指条件。
- **控制点**：`tracking_point`，默认 **`thumb_tip`（大拇指指尖）**；可换 `palm`（手腕+四个掌指关节均值）、`wrist`、`index_tip`。调试叠加层的**洋红色圆圈**就是当前控制点。
- **映射**：`mapping=relative`（默认）：gate 进入瞬间锁定手部锚点与当前光标位置，之后按位移增量移动（不会跳变）；`absolute`：手在画面中的位置直接映射屏幕，只取中间 `active_region=0.6` 为满量程。
- **滤波/死区**：手控有**独立的** One Euro 滤波器（`min_cutoff=0.8`、`beta=0.01`），不共用眼睛滤波器状态；输出位移小于 `deadzone_px=12` 时不更新。
- **安全**：只有 gate OPEN 时手才移动光标；CLOSED 时**光标保持不动**（不回落到眼控，避免手一放下光标乱跳）。`suspend_blink_while_hand=true` 可在手控接管时暂停眨眼点击（默认 false，即“手管移动、眼管点击”）。
- **性能**：`hand_every_n_frames` 可降频检测手（默认 1）；叠加层 `HandFPS` 显示实际手部帧率。

## 5. 光标来源：眼控

- 14 维特征向量（`FEATURE_DIM=14`）：虹膜比例、头姿 yaw/pitch/roll、几何视线 `gaze_yaw/gaze_pitch`、头部尺度等。
- 管线：**特征层**小窗口中值（`feature_median_window=3`）+ EMA（`feature_ema_alpha=0.5`）→ **回归**（特征标准化 + 可选二次项 + Ridge，`alpha` 由头动样本交叉验证选取）→ **屏幕坐标 One Euro**（`min_cutoff=0.5`、`beta=0.002`）→ **死区** `deadzone_px=30` → **注视稳定锁定**（`stability_window=0.3s` 内标准差 < `stability_std_px=1.5` 时锁定光标）。
- 头姿超出校准时记录的范围时，叠加层提示 `HEAD OUT OF RANGE`，并对每帧位移限幅（`out_of_range_step_px=25`）。

## 6. 光标来源：头控（面部朝向）

- `mode=absolute`（默认，角度直接映射屏幕位置，最跟手）或 `velocity`（摇杆式，转头即持续移动）。
- 中性区 `deadzone_deg=4`；满屏偏转 `max_yaw_deg=22` / `max_pitch_deg=16`；`speed_px_s=900`（velocity）；速度曲线 `response=1.6`。
- 对角方向额外增益 `diagonal_boost=0.5`；把脸部左右平移计入水平方向 `translation_weight=0.5` / 满量程 `translation_range=0.25`。
- **`invert_x` / `invert_y` 默认都是 `true`**（本机镜像画面实测两个方向都需反转，改动前先确认）。
- `F4` 一键基准点：把当前头姿设为屏幕中心（坐姿变了随手一按回中）。

## 7. 眨眼点击（眼睛负责，与光标来源无关）

| 连续眨眼次数 | 动作 |
|---|---|
| 1 | 无（视为自然眨眼） |
| 2 | 左键单击 |
| 3 | 右键单击 |
| 4 | 左键双击 |
| 5 | 开始/结束拖拽 |
| ≥6 | 忽略 |

- EAR 阈值带迟滞：闭眼 `EAR < 基线 × 0.60`，睁眼 `EAR > 基线 × 0.75`。
- 有效闭眼时长 `0.06~0.50s`；同组最大睁眼间隔 `group_gap=0.5s`（**这是动作的固有延迟来源**）。
- 点击位置取「序列第一次闭眼开始前 `freeze_lookback=0.3s`」的光标位置，眨眼过程中光标冻结，因此点击不漂移。
- 另有「注视停留点击」模式（`click.mode=dwell` / `both`），参数 `dwell_time=1.2s`、`dwell_radius=40px`。

## 8. 校准流程

1. **面部标定**（`face_profile.enabled=true` 且无 `data/face_profile.json`）：正对镜头、中性表情，采集约 **150** 有效帧（丢脸/异常帧丢弃），对约 20 个稳定点（额头、鼻梁、鼻尖、鼻翼、眼角、嘴角、下巴）取 3D 中位数，用两外眼角距离归一化，存 `data/face_profile.json`（覆盖前备份）。`--recalibrate-face` 可单独重做。
2. **初始基线**：保持自然睁眼约 1.5 秒。
3. **9 点静止采样**：每点 `settle_time=1.0s` + `sample_time=1.5s`，每点至少 10 个有效样本，不足自动重采。
4. **头动补偿采样**（`head_motion_calibration.enabled=true`）：中心+四角附近 **5** 个点，每点 `per_point_seconds=8s`；眼睛盯住该点、头部缓慢向上/下/左/右转一圈并画小圈；记录虹膜特征、yaw/pitch/roll、鼻尖平移与尺度；丢脸/闭眼/头姿超范围（`max_yaw_deg=35`、`max_pitch_deg=30`、`max_roll_deg=30`）的帧丢弃。
5. **最终基线** + **眨眼练习**（依次提示 2/3/4 次眨眼，练习期间不触发真实动作，ESC 可跳过）。
6. 结束后打印**静止样本 / 头动样本各自的平均误差（px）**，写入 `data/calibration.json`；整体误差 > 250px 会提示重做。

**模型版本 `MODEL_VERSION = 3`**：校准文件版本或屏幕分辨率不匹配时，会提示「请重新校准」，**不会崩溃**。

## 9. 调试叠加层

- 文字：`EAR / FPS / Status / Mode / Blinks / Raw / Filt / Jitter 1s / Head yaw-pitch-roll / Gaze / Reproj / FaceX / Hand / HandFPS / Ptr` 等。
- 图形：人脸关键点（黄）、手部 21 点骨架（青）与**洋红色追踪点**、头部朝向**三色轴**（X 红 / Y 绿 / Z 蓝）。
- 叠加层文字一律英文（避免 OpenCV 中文乱码）。
- 叠加层坐标映射只使用**摄像头帧的实际 (w, h)**，不使用屏幕坐标或头姿补偿值（有回归测试锁死）。

## 10. 热键

| 键 | 作用 |
|---|---|
| `F9` | 暂停/恢复（暂停后只能用 F9 恢复） |
| `F10` | 退出 |
| `F8` | 重新校准 |
| `F7` | 开关点击功能 |
| `F6` | 循环点击模式 `blink_sequence → dwell → both → none` |
| `F5` | 眼控 ↔ 头控（回落来源）；`hand` 模式下不影响手控 |
| `F4` | 头控一键基准点（当前头姿 = 屏幕中心） |

## 11. 配置项（`config.yaml`）

```yaml
camera:            # index/width/height/fps/mirror
tracking:          # 眼控：min_cutoff, beta, d_cutoff, lost_face_timeout,
                   #      deadzone_px, feature_median_window, feature_ema_alpha,
                   #      stability_window, stability_std_px
click:             # mode, close_ratio, open_ratio, blink_min/max_duration, group_gap,
                   # max_blinks, freeze_lookback, cooldown, actions{1..6}, dwell_time, dwell_radius
calibration:       # grid=3, margin, settle_time, sample_time, poly_degree, ridge_alpha, file, practice_blinks
head_motion_calibration:
                   # enabled, points=5, per_point_seconds=8, settle_time,
                   # max_yaw_deg=35, max_pitch_deg=30, max_roll_deg=30, pose_margin_deg=5,
                   # out_of_range_step_px=25, ridge_alphas, cv_folds
face_profile:      # enabled, samples=150, eyeball_offset=0.5, focal_scale=1.0,
                   # reprojection_error_px=8, smoothing_alpha=0.6, file
head_control:      # enabled, default_source=eye, mode=absolute, deadzone_deg=4,
                   # max_yaw_deg=22, max_pitch_deg=16, speed_px_s=900, response=1.6,
                   # smoothing_alpha=0.6, invert_x=true, invert_y=true,
                   # diagonal_boost=0.5, translation_weight=0.5, translation_range=0.25
hand_control:      # enabled=true, pointer_source=hand, mirror_handedness=false,
                   # open_ratio=1.1, finger_spread_min=0.25, enter_frames=5, exit_frames=5,
                   # lost_timeout=0.3, mapping=relative, gain=2.4, active_region=0.6,
                   # min_cutoff=0.8, beta=0.01, deadzone_px=12.0, hand_every_n_frames=1,
                   # suspend_blink_while_hand=false, tracking_point=thumb_tip, require_thumb=true
safety:            # pause_key=f9, quit_key=f10, recalibrate_key=f8,
                   # toggle_click_key=f7, cycle_mode_key=f6, cursor_key=f5, baseline_key=f4
debug:             # show_window=true, log_level=INFO, log_file=data/run.log
```

配置读取规则：缺失字段取默认值，**未知字段会报错**，非法值抛中文 `ValueError`。

## 12. 代码结构（`eyemouse/`）

| 模块 | 职责 |
|---|---|
| `app.py` | 主循环与状态机：整合摄像头、关键点、特征、校准、点击、鼠标、热键、界面；含手控路由 `resolve_cursor_driver` |
| `camera.py` | 摄像头封装：打开/读帧（统一镜像）/释放，失败给中文提示 |
| `landmarks.py` | MediaPipe FaceMesh 封装与关键点索引常量 |
| `features.py` | EAR、虹膜比例、14 维视线特征向量 |
| `head_pose.py` | solvePnP 头姿估计（个人模板优先，回退通用模板；时间平滑、重投影误差可信度） |
| `face_profile.py` | 个人面部标定（3D 中位数模板） |
| `gaze_geometry.py` | 几何视线：眼球中心 + 头坐标系视线角 |
| `calibration.py` | 9 点/头动校准流程、Ridge 回归、JSON 存读、眨眼练习 |
| `click_detector.py` | 连续眨眼计数状态机 + 注视停留（纯逻辑） |
| `filters.py` | One Euro Filter |
| `head_control.py` | 面部朝向 → 光标（absolute / velocity） |
| `hand_tracker.py` | MediaPipe Hands 封装（只取指定手，默认右手） |
| `hand_gesture.py` | 张开手掌判定 + `OpenPalmGate` 滞回状态机（纯逻辑） |
| `hand_pointer.py` | 手控映射（relative/absolute）、追踪点选择、独立滤波与死区 |
| `mouse.py` | 鼠标控制（pyautogui 真实实现 + dry-run 实现） |
| `hotkeys.py` | 全局热键 |
| `ui.py` | OpenCV 界面：校准窗口、眨眼练习、调试叠加层 |
| `config.py` | 配置解析与校验（dataclass + 中文报错） |

## 13. 数据文件与隐私

- `data/calibration.json`：校准样本、回归系数、头姿范围、静止/头动误差。覆盖前自动备份为 `data/calibration.<时间戳>.bak.json`。
- `data/face_profile.json`：个人面部 3D 模板（含版本号、点索引、采样帧数、质量指标），覆盖前备份。
- `data/run.log`：运行日志（只记录动作/坐标/状态，不含图像）。
- **不保存任何图像**，不上传。校准文件用 JSON（不用 pickle），加载时重新 fit。

## 14. 测试

```
.\.venv\Scripts\python.exe -m pytest -q
```

当前 **179 passed**。测试全部为合成数据/纯逻辑，**不开摄像头、不动真实鼠标**：

| 测试文件 | 覆盖点 |
|---|---|
| `test_config.py` | 默认值、真实 config.yaml、非法值报错 |
| `test_features.py` | EAR、虹膜比例、14 维特征、NaN 处理 |
| `test_filters.py` | One Euro：静止稳定、阶跃收敛、reset、dt<=0 |
| `test_smoothing.py` | 特征层中值/EMA、抖动统计、注视锁定 |
| `test_click_detector.py` | 连续眨眼计数、分组、dwell |
| `test_calibration.py` | 合成数据拟合、保存/加载、分辨率校验、备份、JSON 安全 |
| `test_face_profile.py` | 面部模板、PnP（角度误差 < 1°）、模板优于通用、角度回绕、旧模型降级 |
| `test_head_control.py` | 摇杆速度、绝对映射、方向反转、来源切换、配置校验 |
| `test_hand_control.py` | 张开/握拳/旋转不变、gate 滞回与丢失超时、relative/absolute、追踪点、`require_thumb`、配置校验 |
| `test_ui_overlay.py` | 叠加层坐标映射回归（校准前后一致）、`_draw_head_axis` staticmethod 回归 |
| `test_tools.py` / `test_audit.py` | 地址表工具、`record_env` 自检、哈希链与受保护删除 |

> ⚠️ 若 `pytest -q` 报 `PermissionError [WinError 5]`（临时目录 ACL 异常，见第 16 节），加参数：
> `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp`

## 15. 工程机制（务必遵守）

- **地址表**：每次改动都要登记 ——
  `python tools\log_change.py --type 修改文件 --path <绝对路径> --note <说明> --rollback <回滚方式>`
  写入 `docs/CHANGE_MANIFEST.md`（人读）与 `docs/change_manifest.json`（机读，含 sha256）。
- **审计日志** `audit_logs/`：只追加、带哈希链，**永不删除**；校验 `python tools\audit_log.py --verify-chain`。
- **删除**：工作区内一切删除必须走 `python tools\safe_delete.py <路径>`（拒绝工作区外、`audit_logs/` 与工作区根目录）。
- **环境自检**：`python tools\record_env.py --refresh` 刷新概览；`--verify` 校验登记文件与 sha256（退出码 0 为通过）。
- `tools/diagnose_overlay_mapping.py`：叠加层坐标映射的最小复现脚本（合成数据、不开摄像头）。

## 16. 已知问题与坑（开发者必读）

1. **本沙箱的 0o700 目录 ACL 问题**：在受限沙箱里以 POSIX `mode=0o700` 新建目录会变成「无法列举、无法删除」的目录，而 pytest 的临时目录硬编码 0o700，导致全量测试报 31 个 tmp_path 错误。绕行：`--basetemp` 指向工作区内目录，并用 `.tmp\pytest_mode_patch.py`（沙箱内一次性补丁，用 `-p pytest_mode_patch` 加载）给目录模式补上组/其他位。**在正常（非沙箱）终端里不需要这些**。遗留的坏目录：`.pytmp`、`.tmp\pt_run1`、`.tmp\pytest-of-24224`、`.tmp\d700`、`.tmp\p700`（需要管理员权限才能删除）。
2. **镜像与左右手**：`camera.mirror=true` 时画面已是自拍视角，MediaPipe 的 handedness 标签即正确 → `hand_control.mirror_handedness` 必须为 `false`；两者配错会把左手当右手（曾出现过该 bug，已有回归测试）。
3. **`_draw_head_axis` 的 staticmethod 坑**：该方法曾丢失 `@staticmethod`，经实例调用时 `self` 被当作 `canvas` 传入，抛 `TypeError` 导致程序启动即退出（`data/run.log` 可见）。已修复并有回归测试；新增这类「纯函数式绘制」方法时注意别把装饰器让给相邻方法。
4. **z 深度是相对估计**：面部模板与几何视线的 z 以图像宽度为单位，不是毫米真值；`eyeball_offset`、`focal_scale` 是经验参数，只保证相对改善。
5. **眨眼动作有固有延迟**（`group_gap` 约 0.5s）；单次自然眨眼默认不触发任何动作。
6. **手控是相对映射**：反复朝同一方向挥手会把光标累积到屏幕边缘，需要把手移回有效范围。
7. **大拇指指尖比手掌中心抖**：若觉得飘，调大 `deadzone_px`、调小 `min_cutoff`/`beta`，或把 `gain` 从 2.4 略降；也可 `tracking_point: "palm"`。
8. **面部模板会漂移**：发型/表情/时间变化后建议 `--recalibrate-face`。
9. **`mediapipe` 会改变 opencv 版本**（见第 2 节），排查 `cv2` 行为时以运行时版本为准。
10. **仅支持主显示器**，多显示器未适配。
11. **平台限制**：macOS 需手动授予摄像头与辅助功能权限；Linux Wayland 下 `pynput`/`pyautogui` 可能失效，建议 X11。
12. `F5` 在 `pointer_source=hand` 时不影响手控（手控由 gate 决定）；它只在 `eye`/`hybrid` 下切换回落来源。
13. 帧率低于约 20 FPS 时眨眼识别会变差，可降低分辨率或用 `--no-window`。

## 17. 待办 / 待真机验证

- [ ] 真机验证手控：拇指追踪手感、gate 进入/退出是否自然、与眨眼点击并行是否互相干扰。
- [ ] 确认默认 `gain=2.4` 在目标屏幕上不抖（否则按第 16.7 条调参）。
- [ ] 在目标机器上重跑一次完整校准（面部标定 + 9 点 + 头动 + 眨眼练习），确认分项误差。
- [ ] Python 3.12.8 与任务书 3.10/3.11 的偏离已记录在 README「设计决定」，如需合规需在 3.10/3.11 环境复测。
- [ ] 多显示器 / 高 DPI 缩放场景未验证。