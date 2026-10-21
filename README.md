# EyeMouse：用眼睛代替鼠标

用普通笔记本或 USB 摄像头（RGB，无需红外）追踪用户视线，实现「看哪里、光标到哪里」，
并用**连续眨眼的不同次数**触发左键、右键、双击、拖拽等鼠标动作。全部处理在本地完成，
不上传、不保存任何摄像头图像，只保存校准得到的数值特征。

## 功能特性

- 视线控制屏幕鼠标光标移动（特征层平滑 → 回归 → 屏幕坐标 One Euro 滤波 + 死区 + 注视稳定锁定）。
- 连续眨眼计数触发不同动作，单次自然眨眼不触发。
- 可选「注视停留点击」模式（dwell）。
- 9 点静止校准 + 5 点头动补偿校准，结果以 JSON 保存并可复用；屏幕分辨率变化时要求重新校准。
- 个人面部标定：正对镜头采集约 150 帧，对 20 个稳定点取 3D 中位数生成个人模板，用于个性化头姿（PnP）
  与几何视线估计；无模板时自动回退通用模板。
- 面部朝向控制光标（新增）：把头部 yaw/pitch 映射为光标移动，`absolute`（角度直接映射屏幕位置，最「跟手」：
  头回正光标回正，本项目默认）或 `velocity`（转头即移动的摇杆式）；按 F5 在「眼控」与「头控」之间切换，
  **眼控仍是默认且完整保留**，两者共用同一套连续眨眼点击。
- 一键基准点校准（F4）：头控模式下把当前头姿与脸位设为零点（对应屏幕中心），坐姿变了随手一按即可回中。
- 头控增强：`diagonal_boost` 让左下/右下等对角方向更灵敏（默认 0.5，用「自然对角转头只到各轴 75%」
  的合成测试反推）；`translation_weight/translation_range` 把脸在画面里的左右平移也计入水平映射，
  提供更细的横向控制。调试叠加层新增 `FaceX` 显示脸部水平中心。
- 右手控制光标（新增）：右手**张开手掌**即接管光标，采用相对位移映射（进入瞬间锁定参考点，避免跳变），
  默认**以大拇指指尖为控制点**（`hand_control.tracking_point` 可切回手掌中心 `palm` 等）；
  手部拥有独立的 One Euro 滤波与死区；握拳、四指并拢或不满足张开判定即交还，手离开画面超时立即交还。
  默认 `pointer_source: hand`，此时**眼睛不再移动光标，但仍完整负责连续眨眼点击/双击/右键/拖拽**；
  `hybrid` 下手张开由手接管、否则回眼控。可用 `python main.py --hand-test` 先单独排错。
- 几何视线：由眼角中点沿头坐标系 z 轴后移得到眼球中心，计算头坐标系下的 `gaze_yaw/gaze_pitch`
  （双眼平均），与头姿、尺度一起进入 14 维特征向量。
- 眼镜标记六自由度追踪（阶段一，默认关闭）：用固定在镜框上的已知尺寸 ArUco 标记估计眼镜相对摄像头的
  三维旋转与平移，并提供无鼠标自检工具 `--glasses-test`。**本轮只输出位姿、不接管真实光标**，
  且不改变上面任何默认控制方式。
- 安全机制：F9 暂停、F10 退出、F8 重新校准；暂停/丢脸/退出时自动释放拖拽左键。
- 「环境与变更地址表」与「工作区外操作审计日志」，随时可自检。

## 环境要求与安装

### Python 版本

任务书要求 Python 3.10 或 3.11。本机只安装了 Python 3.12.8，且 `mediapipe==0.10.14`
官方提供 `cp312` wheel（已实测安装并运行成功），因此本项目在 Python 3.12.8 下开发与验证，
详见「设计决定」。若你的机器上有 3.10/3.11，同样可用。

### 创建虚拟环境并安装依赖

Windows（PowerShell）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --no-cache-dir -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --no-cache-dir -r requirements.txt
```

也可以不激活，直接用项目内解释器执行所有命令，例如
`.\.venv\Scripts\python.exe main.py`。**不要把依赖装到全局环境。**

## 快速开始

请务必按以下顺序首次运行：

1. 摄像头排错：`python main.py --camera-test`
   在弹出的窗口中确认能看到人脸关键点（黄色圆点）。按 ESC 退出。
2. 无鼠标演练：`python main.py --dry-run`
   不真正控制鼠标，只在校准与跟踪时打印动作日志，用于熟悉校准与眨眼节奏。
3. 正式运行：`python main.py`
   启动时会打印热键说明；若没有校准文件会先进入 9 点校准。

其他常用参数：

| 参数 | 作用 |
|---|---|
| `--config PATH` | 指定配置文件（默认 `config.yaml`） |
| `--recalibrate` | 忽略已有校准文件，强制重新校准 |
| `--recalibrate-face` | 只重做个人面部标定（3D 模板），沿用已有屏幕校准 |
| `--dry-run` | 不真正控制鼠标，只打印动作 |
| `--no-window` | 不显示调试窗口（校准时也无全屏界面） |
| `--camera-test` | 只打开摄像头显示关键点，不控制鼠标 |
| `--log-level LEVEL` | 覆盖日志级别，如 `DEBUG` |
| `--pointer-source {eye,hand,hybrid}` | 覆盖 `hand_control.pointer_source`（默认 `hand`） |
| `--hand-test` | 只打开摄像头显示右手 21 点与 Gate 状态，不控制鼠标 |
| `--write-charuco-board [PATH]` | 导出可打印的 ChArUco 标定板 PNG（默认 `data/charuco_board.png`） |
| `--write-aruco-marker [PATH]` | 导出眼镜 ArUco **单标记**打印图纸（黑框边长取自 `glasses_tracking.marker_size_m`，默认 30 mm 黑框 + 10 mm 白边，默认输出 `data/aruco_marker_id0_30mm.png`） |
| `--calibrate-camera` | 摄像头内参标定（ChArUco），只保存数值参数，不控制鼠标、不触发点击 |
| `--glasses-test` | 眼镜标记自检：只显示位姿/重投影/坐标轴/静止抖动，**不创建鼠标控制、不触发点击** |

## 校准指南

- 环境：光线均匀充足，避免逆光与屏幕强反光；摄像头置于屏幕上方中央，正对脸部。
- 姿势：坐姿稳定，距离屏幕约 **50~70 cm**，头部尽量正对摄像头、少晃动。
- 流程：
  0. **面部标定**（`face_profile.enabled=true` 且尚无 `data/face_profile.json` 时）：
     屏幕提示 `Face calibration: look straight at the camera, neutral expression`。
     请正对镜头、保持中性表情，程序会采集约 150 个有效帧（丢脸/异常帧自动丢弃），对 20 个稳定点
     （额头、鼻梁、鼻尖、鼻翼、眼角、嘴角、下巴）的 3D 坐标取中位数，并用两外眼角距离归一化，
     生成个人面部模板并保存到 `data/face_profile.json`（覆盖前自动备份）。可用 `--recalibrate-face` 单独重做。
  1. **初始基线**：屏幕提示 `Look at the screen, keep eyes open`，保持自然睁眼约 1.5 秒。
  2. **9 点静止采样**：依次注视屏幕上出现的圆点（红色收缩动画，稳定后变绿），每点采样 1.5 秒。
     每个点至少需要 10 个有效样本，样本不足会自动重采一次。
  3. **头动补偿采样**（`head_motion_calibration.enabled=true` 时）：依次注视中心与四角附近的 5 个点，
     每点约 8 秒；眼睛盯住该点的同时，头部缓慢向上、下、左、右转一轮并画一个小圈。程序会记录
     虹膜特征、yaw/pitch/roll、鼻尖平移与头部尺度；丢脸、闭眼或头姿超出合理范围的帧会被丢弃。
  4. **最终基线**：用整个校准过程的数据重新计算睁眼 EAR 基线，用于后续眨眼识别。
  5. **眨眼练习**：依次提示 2/3/4 次眨眼，实时显示识别次数与对应动作，练习期间不触发真实动作。
     按 ESC 可跳过。
- 校准结束后会做「留一点交叉验证」，分别打印**静止样本与头动样本的平均误差（px）**，并写入
  `data/calibration.json`；若整体误差 > 250 px，会提示校准质量较差，建议重来。
- 正式运行时如果头姿超出校准范围，调试窗口会显示 `HEAD OUT OF RANGE`，并对光标位移做限幅。

## 眼镜标记六自由度追踪（阶段一）

这是「头部**指向**」追踪，不是眼球注视追踪：固定标记只能给出眼镜的刚体位姿，
并不能说明眼睛在看哪里。阶段一**只输出位姿，不控制真实光标**，也不会改变默认的
`hand_control.pointer_source`（默认仍是 `hand`）。

### 硬件准备

- 一副眼镜或轻便刚性支架；一块已知边长的 ArUco 标记（默认 `DICT_5X5_50`、`id=0`、边长 30 mm）。
- 标记贴在镜框或支架的**刚性**位置，尽量**不遮挡眼睛**、不影响眨眼检测，也不要贴在会弯折的镜腿上。
- 标记必须平整、无褶皱、无反光；打印或裁切后**用直尺实测边长**，并把实测值写进
  `glasses_tracking.marker_size_m`（程序不猜尺寸，尺寸错了平移量就整体按比例错）。
- 摄像头保持当前安装位置（屏幕上方、正对用户）；**移动摄像头或改变变焦/裁切后必须重新标定内参**。

### 打印眼镜 ArUco 单标记（30 mm 黑框 + 白边）

```powershell
.\.venv\Scripts\python.exe main.py --write-aruco-marker data\aruco_marker_id0_30mm.png
```

- 图纸参数直接取自 `glasses_tracking`（`dictionary`、`marker_id`、`marker_size_m`），默认
  `DICT_5X5_50`、`id=0`、**黑色外框边长 30.00 mm**，四周各留 **10.0 mm 纯白边**
  （ArUco 必须有白边才稳定；白边小于一格时会自动放大到一格）。
- 默认输出 `data/aruco_marker_id0_30mm.png`：整张纸 123.0 × 150.0 mm（1464 × 1785 px，
  **1 像素 = 0.0840 mm**，PNG 物理分辨率元数据 = 11900 px/m ≈ 302.26 dpi），
  图上自带 0–100 mm 毫米刻度参考条与全部打印说明（图内文字为英文，`cv2.putText` 不支持中文）。
- 想改尺寸就先改 `glasses_tracking.marker_size_m`（单位：米）再重新导出，这样「打印的标记」
  与「程序里的标记」永远一致；覆盖同名文件不备份（图纸可由配置随时重建）。
- 本命令**只写这一张 PNG**：不开摄像头、不控制鼠标、不改变任何追踪逻辑。

**量尺方式（打印后必须做）**：

1. 打印对话框选 **100% / 实际大小（Actual size）**，**不要**选「适合页面 / Fit to page」。
2. 用**真尺**量图下方参考条上 **`0` 与 `10` 两个刻度之间**（= 100.0 mm）：若不是 100.0 mm，说明整张图被缩放，请重新打印；
   确实无法按 100% 打印时，直接做第 3 步并按实测值配置。
3. 用**真尺**量**黑色外框**边长（黑边外缘到外缘，量到黑边最外侧），把实测值换算成米写进
   `glasses_tracking.marker_size_m`。程序不猜尺寸：尺寸写错，平移量会整体按比例错。
4. 打印图**不要镜像翻转**（导出朝向就是摄像头看到的朝向）；标记贴平、无反光，
   不遮挡眼睛与眨眼检测区域。

### 第一步：打印标定板

```powershell
.\.venv\Scripts\python.exe main.py --write-charuco-board data\charuco_board.png
```

- 屏幕会打印方格边长、标记边长与**整板物理尺寸**；默认 8×6、方格 25.00 mm → 整板 200.0 × 150.0 mm。
- 打印时必须 **100% 实际尺寸（实际大小）**，**不要**选「适合页面 / Fit to page」，否则方格尺寸会变。
- 打印后**必须用直尺实测**若干方格边长，与上面数值一致才能用于标定。
  该 PNG 按 4000 px/m 精确渲染（1 像素 = 0.25 mm），并写入物理分辨率元数据（约 101.6 dpi），
  导出时还会自己实测一次方格像素尺寸，偏差超过 0.5 px 会直接拒绝导出。

### 第二步：摄像头内参标定

```powershell
.\.venv\Scripts\python.exe main.py --calibrate-camera
```

- 窗口中完整、清晰地对焦标定板，**空格**采集一个视图，**C** 完成标定并保存，**R** 清空重来，**ESC/Q** 退出。
- 需要至少 `min_views`（默认 15）个**倾角与画面位置都不同**的有效视图；重复视角会被拒绝并提示。
- 标定只用**未镜像的原始画面**；窗口里看到的镜像显示只影响显示，不参与计算。
- 结果保存到 `data/camera_calibration.json`（覆盖前自动备份为 `camera_calibration.<时间戳>.bak.json`），
  含 schema 版本、板参数、标定分辨率、逐视图与整体重投影 RMS、覆盖网格数。
- **`rms_px` 只是重投影残差，不是参数协方差，也不代表绝对位姿精度。**
- 标定分辨率与运行时分辨率不一致时，程序**拒绝输出位姿**并提示重新标定，不会静默复用。

### 第三步：无鼠标自检

```powershell
.\.venv\Scripts\python.exe main.py --glasses-test
```

- 只开摄像头与调试窗口：**不实例化鼠标控制、不注册任何点击动作、不保存图像**。
- 叠加层显示：标记边界与 ID、三色坐标轴（X=红 Y=绿 Z=蓝）、`Status`、`Reproj`、`Translation`（mm）、
  `Yaw/Pitch/Roll`、`TrackingFPS`、有效观测比例、最近窗口的静止抖动，以及选解/失效原因。
- 有效位姿为绿色；丢标记后短时间内保留的最后姿态标为 **`STALE`（黄色）**，它不是有效观测。
- 按键：`ESC` / `q` / `F10` 退出，`m` 切换显示镜像（只影响显示），`r` 重置滤波与统计，`s` 立即打印统计。
- 每隔 `stats_period_s`（默认 2 秒）打印一次统计：有效帧率、有效比例、状态计数、
  静止窗口的位置标准差（mm）与旋转角抖动（度，用旋转几何计算，不会因跨 ±180° 得到假值）。
- 若内参文件缺失，程序提示先运行 `--calibrate-camera`；若配置分辨率与标定分辨率不一致，会先给出警告。

### 标记尺寸与精度提示

- 标记在画面里越小（像素越少）、越倾斜（侧转）、越反光或被手遮挡，位姿精度越差；
  30 mm 标记在 0.5 m 处、fx≈1000 时只有约 60 px，已接近可用下限，建议尽量靠近摄像头或换更大标记。
- 单个正方形平面标记存在 IPPE 平面二义性（两个镜面对称解）。合成数据实测：两解的逐帧重投影 RMS
  差中位数只有约 0.17 px，而角点噪声本身有 0.25 px 量级，所以**单帧误差根本不足以区分两解**。
  实现上：有近期参考姿态时用**时间连续性**在都合格的候选之间择一；
  冷启动/长时间丢失后用**多帧证据累积**（`acquisition_frames`、`ambiguity_evidence_px`）判定；
  两支确实无法区分时**一直报 `AMBIGUOUS`**，不输出可信姿态。
- 平移单位统一为米，界面按毫米显示；深度（z）是相对估计，用于比较稳定性，不等同于卷尺量出的真值。

### 数据文件格式（阶段一）

`data/camera_calibration.json`（JSON，非 pickle；覆盖前自动备份）：

| 字段 | 说明 |
|---|---|
| `schema_version` | 文件结构版本；未来不兼容时加载会中文报错并要求重新标定 |
| `saved_at` | 保存时间（本地时间字符串） |
| `unit` | 固定 `meter` |
| `image_size` | `[width, height]`，标定分辨率；与运行分辨率不一致时拒绝使用 |
| `board` | `{dictionary, squares_x, squares_y, square_length_m, marker_length_m, unit}` |
| `camera_matrix` | 3×3 内参矩阵（只对未镜像原始画面有效） |
| `dist_coeffs` | 一维畸变系数 |
| `metrics.rms_px` | 整体重投影 RMS（**只是残差，不是参数协方差/绝对精度**） |
| `metrics.per_view_rms_px` | 逐视图重投影 RMS 列表 |
| `metrics.num_views` / `metrics.coverage_cells_hit` | 有效视图数 / 命中覆盖网格数 |

眼镜追踪本身不新增数据文件（阶段一只输出位姿）；个人面部模板仍使用 `data/face_profile.json`，
眼控校准仍使用 `data/calibration.json`，三者互不复用。
`data/aruco_marker_id0_30mm.png` 只是可打印图纸（纯图案、不含任何摄像头画面），不是运行时数据文件。

### 真机验证记录表（阶段一，建议按此表逐项勾验）

运行 `.\.venv\Scripts\python.exe main.py --glasses-test` 后按下表逐项记录（`m` 可切换显示镜像）。

| # | 验证项 | 操作 | 期望现象 | 实测 | 通过 |
|---|---|---|---|---|---|
| 1 | 打印尺寸 | 直尺实测 3 个方格 | 均等于 `square_length_m`（默认 25.00 mm） |  |  |
| 2 | 标记尺寸 | `--write-aruco-marker` 导出后 100% 打印，直尺实测黑框边长与 100 mm 参考条 | 与 `glasses_tracking.marker_size_m` 一致（参考条 = 100.0 mm） |  |  |
| 3 | 内参标定 | `--calibrate-camera` 采集 ≥15 个不同倾角视图 | 保存成功，逐视图 RMS 合理（≪1.5 px） |  |  |
| 4 | 分辨率一致 | 标定后直接跑 `--glasses-test` | 无 `CALIBRATION_MISMATCH`、无分辨率警告 |  |  |
| 5 | 静止抖动 | 保持静止 10 秒，按 `s` | `dPos`（mm）与 `dRot`（度）越小越好，记录数值 |  |  |
| 6 | 位姿有效性 | 正常坐姿左右/上下转头 | `Status: TRACKING`（绿色），`Reproj` 保持在阈值内 |  |  |
| 7 | 坐标轴方向 | 观察三色轴 | X=红（图像右）、Y=绿（图像下）、Z=蓝（朝摄像头，投影很短） |  |  |
| 8 | 镜像规则 | 按 `m` 切换 | 画面与标记边框一起镜像，几何数值（Reproj/Trans/Yaw）不变 |  |  |
| 9 | 短时遮挡 | 用手遮住标记 0.5 秒再放开 | 遮挡时黄色 `STALE`（非有效），放开后经 `STABILIZING` 恢复 `TRACKING` |  |  |
| 10 | 双解歧义 | 正对摄像头保持不动 | 若显示 `AMBIGUOUS`，按提示轻微转头或保持可见等待证据累积 |  |  |
| 11 | 帧率 | 观察 `TrackingFPS` | 与 `camera.fps` 同量级（眼镜追踪本身开销很小） |  |  |
| 12 | 无鼠标副作用 | 全程运行 `--glasses-test` | 光标不动、无任何点击发生 |  |  |

## 连续眨眼操作指南

| 连续眨眼次数 | 动作 |
|---|---|
| 1 次 | 无（视为自然眨眼） |
| 2 次 | 左键单击 |
| 3 次 | 右键单击 |
| 4 次 | 左键双击 |
| 5 次 | 开始 / 结束拖拽（按下 / 释放左键） |
| 6 次及以上 | 忽略 |

**节奏建议**：连续眨眼时每次闭眼约 0.1~0.2 秒，两次之间尽量快地睁开（间隔 < 0.5 秒），
全部眨完后保持睁眼等待约 0.5 秒，动作即会执行。

**为什么有延迟**：程序需要等最后一次眨眼后 `group_gap`（默认 0.5 秒）内不再有新的眨眼，
才能确认「这一组到底眨了几次」。这是区分「自然单次眨眼」与「有意连续眨眼」的代价。

**为什么点击位置不漂移**：点击位置取「序列第一次闭眼开始前 `freeze_lookback`（默认 0.3 秒）」
那一刻的光标位置；眨眼序列进行中光标会被冻结，因此眨眼过程中光标不会乱跑。

## 热键表

| 热键 | 作用 |
|---|---|
| F9 | 暂停 / 恢复（暂停后不再移动鼠标，**只能用 F9 恢复**） |
| F10 | 退出程序 |
| F8 | 重新校准 |
| F7 | 开关点击功能 |
| F6 | 循环切换点击模式：`blink_sequence` → `dwell` → `both` → `none` |
| F5 | 循环切换回落光标来源：`eye`（眼控）↔ `head`（面部朝向）。仅在 `pointer_source` 为 `eye`/`hybrid` 时生效；`hand` 模式下 gate 关闭时光标固定不动 |
| F4 | 一键基准点校准（头控：把当前头姿设为零点，即屏幕中心） |

## 配置项说明

所有配置在 `config.yaml`，缺失字段使用默认值，非法值会抛出带中文说明的错误。

- `camera`：`index` 摄像头序号，`width/height/fps` 采集参数，`mirror` 是否左右镜像。
- `tracking`：`min_cutoff/beta/d_cutoff` 屏幕坐标 One Euro Filter 参数；`lost_face_timeout` 丢脸超时；
  `deadzone_px` 死区像素（默认 30）；`feature_median_window/feature_ema_alpha` 特征层小窗口中值 +
  EMA 平滑（分别设为 1 即可关闭该级）；`stability_window/stability_std_px` 注视稳定判定窗口与抖动阈值
  （窗口内抖动小于阈值时锁定光标，抑制静止抖动）。
- `click`：`mode` 点击模式；`close_ratio/open_ratio` 闭眼/睁眼阈值（相对基线，带迟滞）；
  `blink_min_duration/blink_max_duration` 有效闭眼时长范围；`group_gap` 同组眨眼最大间隔；
  `max_blinks` 最大计数；`freeze_lookback` 点击位置回看时长；`cooldown` 动作冷却；
  `actions` 次数到动作的映射；`dwell_time/dwell_radius` 停留点击参数。
- `calibration`：`grid` 校准网格（3 = 9 点）；`margin` 边缘留白比例；`settle_time/sample_time`
  每点等待与采样时长；`poly_degree/ridge_alpha` 回归模型参数；`file` 校准文件（必须位于 `data/`）；
  `practice_blinks` 是否进入眨眼练习。
- `head_motion_calibration`：`enabled` 是否追加头动补偿校准；`points` 头动注视点数（中心 + 四角，默认 5）；
  `per_point_seconds` 每点采样时长；`settle_time` 每点对齐时间；`max_yaw_deg/max_pitch_deg/max_roll_deg`
  采样时允许的头姿范围（超出丢弃）；`pose_margin_deg` 运行时判定超范围的边界余量；
  `out_of_range_step_px` 超范围时每帧最大位移（限幅）；`ridge_alphas/cv_folds` 岭回归交叉验证候选与折数。
- `face_profile`：`enabled` 是否启用个人面部标定；`samples` 目标有效帧数（默认 150）；
  `eyeball_offset` 眼球中心沿头坐标系 z 轴后移比例（相对两外眼角距离，默认 0.5）；
  `focal_scale` 焦距 = 图像宽度 × 该系数（默认 1.0）；`reprojection_error_px` 重投影误差阈值，
  超过则标记该帧头姿不可信（默认 8.0）；`smoothing_alpha` 头姿角度时间平滑系数（默认 0.6，1=不平滑）；
  `file` 面部模板路径（必须位于 `data/`，默认 `data/face_profile.json`）。
- `head_control`：`enabled` 是否允许面部朝向控制光标；`default_source` 启动时的光标来源
  （`eye` 默认 / `head`）；`mode`=`absolute`（角度直接映射位置，最跟手）或 `velocity`（摇杆式，转头即持续移动）；
  `deadzone_deg` 中性区角度（absolute 下此范围内回到中心，velocity 下不动）；`max_yaw_deg/max_pitch_deg`
  absolute 满屏偏转角度 / velocity 达到最大速度的角度；`speed_px_s` velocity 最大速度（像素/秒）；
  `response` velocity 速度曲线指数；`smoothing_alpha` 速度平滑；`invert_x/invert_y` 方向反了就置 true；
  `diagonal_boost` 对角方向额外增益（纯对角最多 ×(1+boost)，默认 0.5）；`translation_weight` 脸部左右
  平移计入水平方向的比例（0=不用，负值可翻转，默认 0.5）；`translation_range` 平移满量程（归一化画面
  宽度，越小越灵敏，默认 0.25）。
- `hand_control`：`enabled` 是否启用手控；`pointer_source`=`eye`/`hand`/`hybrid`（默认 `hand`，
  未启用或取值非法时回退眼控）；`mirror_handedness` 是否互换左右手标签（默认 false：`camera.mirror: true`
  时画面已是自拍视角，MediaPipe 标签即正确；若把 `camera.mirror` 关成 false，才需要改成 true）；
  `open_ratio` 张开判定比例（指尖到手腕 / 指节到手腕）；`finger_spread_min` 相邻指尖最小间距（相对掌宽，
  用于排除四指并拢）；`enter_frames/exit_frames` 进入/退出 OPEN 的连续帧数（迟滞）；`lost_timeout` 手丢失
  多久立即退出（秒）；`mapping`=`relative`（相对位移，防跳变）/`absolute`（画面位置直接映射）；`gain` 相对
  位移增益；`active_region` absolute 有效区域比例（默认中间 60%）；`min_cutoff/beta` 手部独立 One Euro
  参数；`deadzone_px` 手控死区（像素）；`hand_every_n_frames` 每 N 帧检测一次手（降 CPU）；
  `suspend_blink_while_hand` 手控接管时是否暂停眨眼点击（默认 false，保持「眼睛只管点击」）；
  `tracking_point` 决定「光标跟着哪个部位走」：`thumb_tip`（大拇指指尖，默认）/`palm`（手掌中心）/
  `wrist`（手腕）/`index_tip`（食指指尖），调试叠加层用洋红色圆圈标出实际追踪点；
  `require_thumb`（默认 true）决定「张开手掌」判定是否必须拇指伸出，设为 false 后手掌开合不再被
  大拇指牵制（四指伸直并分开即可）。
- `safety`：`pause_key/quit_key/recalibrate_key/toggle_click_key/cycle_mode_key/cursor_key/baseline_key` 热键名。
- `camera_calibration`：`dictionary` ArUco 字典；`squares_x/squares_y` 方格行列数（乘积必须为偶数）；
  `square_length_m/marker_length_m` 方格与标记边长（米，必须实测）；`min_views` 有效视图下限；
  `min_corners_per_view` 单视图最少角点数；`coverage_cells/coverage_min_cells` 画面覆盖网格与下限；
  `duplicate_distance` 重复视角判定阈值；`file` 内参文件（必须位于 `data/`，默认 `data/camera_calibration.json`）。
- `glasses_tracking`：`enabled` 是否启用（阶段一默认 false，不影响现有行为）；`marker_id/dictionary/marker_size_m`
  标记参数（尺寸必须实测）；`subpixel_win` 亚像素精化窗口；
  `min_marker_area_px` 标记面积下限；`max_reprojection_error_px` 重投影阈值；
  `ambiguity_reproj_margin_px/ambiguity_angle_deg` 判定「双解歧义」的误差与夹角条件；
  `ambiguity_evidence_px/acquisition_frames/ambiguity_branch_angle_deg` 冷启动多帧证据累积参数；
  `max_linear_speed_m_s/max_angular_speed_deg_s/gap_reset_s` 运动异常拒绝与间隔重置；
  `slerp_alpha/translation_alpha` 旋转（四元数 SLERP）与平移独立平滑系数（1=不平滑）；
  `stabilize_frames` 重新获取后恢复 `TRACKING` 所需的连续有效帧数；`stale_timeout_s` 保留最后姿态的时长；
  `stats_period_s/stability_window_s` 自检统计间隔与静止统计窗口；`compare_facemesh` 是否做可选的
  FaceMesh 抖动对比（默认 false，避免影响帧率；本轮未实现该对比，仅保留配置位）。
- `debug`：`show_window` 是否显示调试窗口；`log_level` 日志级别；`log_file` 日志文件（必须位于 `data/`）。

## 调参指南

- **两次眨眼总被识别成一次或两组** → 调大 `group_gap`（0.6~0.7）。
- **自然眨眼被误识别为指令** → 调小 `close_ratio`（如 0.5），或把 2 次对应的动作改为 `none`、
  从 3 次起步。
- **眼睛较小或戴眼镜，眨眼识别不到** → 把 `blink_min_duration` 放宽到 0.04。
- **眨眼太快识别不到** → 检查帧率，低于 20 FPS 时闭眼帧数不足，可降低分辨率或关闭调试窗口。
- **光标抖动** → 调小 `min_cutoff`（默认 0.5）与 `beta`（默认 0.002）会更稳（代价是更迟钝）；
  `feature_median_window`（默认 3）与 `feature_ema_alpha`（默认 0.5）增大可进一步抑制特征噪声，
  但会带来一点延迟。静止时抖动可调小 `stability_std_px` 让光标更早锁定；光标「发粘」则调大或把
  `stability_window` 调小。
- **光标在静止时轻微游走** → 调大 `deadzone_px`（默认 30），或调小 `stability_std_px`。
- **头一动就偏** → 确认校准时的头动阶段已完成；必要时把 `head_motion_calibration.enabled` 设为 `true`
  重新校准，或调大 `per_point_seconds` 采得更充分；`ridge_alphas` 可加入更大值增强抗过拟合。
- **头姿稍动就提示超范围** → 调大 `pose_margin_deg`（放宽判定）或重新校准扩大范围；
  `out_of_range_step_px` 控制超范围时的限幅强度（越小越安全、越滞后）。
- **注视停留太容易/太难触发** → 调整 `dwell_time` 与 `dwell_radius`。
- **头一转头姿角度就跳** → `face_profile.smoothing_alpha` 调小（默认 0.6）会更平滑但更滞后；
  确认 `refine_landmarks=True`（虹膜点）且面部模板与当前一致，必要时 `--recalibrate-face` 重做。
- **调试窗口重投影误差经常很大 / 头姿被判不可信** → 调大 `face_profile.reprojection_error_px`（阈值），
  或检查光线与是否戴了改变脸型轮廓的配件；`focal_scale` 可微调（默认 1.0，即焦距=图像宽度）。
- **视线角度偏大或偏小** → 调整 `face_profile.eyeball_offset`（默认 0.5）：越小视线角度越敏感。
- **面部标定太慢或太快** → 调整 `face_profile.samples`（默认 150），帧率低时可适当减小。
- **面部朝向控制方向反了** → 把 `head_control.invert_x` / `invert_y` 置为 `true`（`velocity` 与
  `absolute` 两种模式都适用）。
- **头控移动太慢 / 到不了屏幕边缘** → 调大 `speed_px_s`（默认 900），或调小 `deadzone_deg`
  （默认 4）、调小 `max_yaw_deg/max_pitch_deg`（更容易达到满速）。
- **头控太灵敏 / 光标抖** → 调大 `deadzone_deg`、调小 `speed_px_s`，或调小 `smoothing_alpha`
  （默认 0.6，越小越平滑但越滞后）；抖得厉害可把 `mode` 设为 `absolute` 试对比。
- **眼睛上下方向不灵敏** → 按 `F5` 切到面部朝向控制作为替代；眼控逻辑原样保留，再按 `F5` 即可切回。
- **头控像摇杆、不跟手** → 确认 `head_control.mode: "absolute"`（角度↔位置一一对应，最跟手）；
  用 `velocity` 时头朝哪个方向光标就持续滑行，不会停在对应位置。
- **absolute 太灵敏 / 走不满全屏** → 调小 `max_yaw_deg/max_pitch_deg` 更灵敏、更容易到边；调大则更迟钝。
  `deadzone_deg` 控制中心静止区大小（越大越不容易因轻微头动而偏离中心）。
- **头控中位漂移（坐姿变了光标不在中心）** → 按 `F4` 一键把当前头姿设为零点基准。
- **左下/右下等对角方向不够灵敏** → 调大 `head_control.diagonal_boost`（默认 0.5；1.0 时纯对角约灵敏
  2 倍）。单轴（纯左/右/上/下）不受该增益影响。
- **横向想要更灵敏/更细** → 调小 `translation_range`（默认 0.25，越小则脸平移同样距离贡献越大）或调大
  `translation_weight`（默认 0.5）。不想用"脸平移"这一路就设为 0；方向感觉反了用负值。

- **手控太灵敏 / 抖** → 调小 `hand_control.gain`（默认 2.4）、调大 `deadzone_px`（默认 12），
  并把 `min_cutoff`（默认 0.8）/`beta`（默认 0.01）调小会更稳（代价是更迟钝）。
- **手控走不满全屏 / 太迟钝** → 调大 `gain`，`absolute` 模式下调小 `active_region` 或调小 `deadzone_px`。
- **手掌刚进入就跳一下** → 保持 `mapping: "relative"`（每次 gate 进入都以当前光标为起点并锁定参考点）；
  改用 `absolute` 时手一进入光标即跳到手所在位置，属预期行为。
- **左右手判定反了** → 多半是 `camera.mirror` 与 `mirror_handedness` 配错：`camera.mirror: true`（默认）时
  保持 `mirror_handedness: false`；若把 `camera.mirror` 关掉，则要把它改成 `true`。程序只识别右手，左手忽略。
- **光标基准点不对（想换部位）** → 默认以大拇指指尖为准（`tracking_point: "thumb_tip"`）；想改用整个
  手掌就把 `tracking_point` 改成 `"palm"`（还有 `wrist`/`index_tip`）。调试叠加层的洋红色圆圈标出当前
  基准点；若拇指一伸一收就影响开关，把 `require_thumb` 改成 `false`。
- **手一张开就误触发** → 把 `require_thumb` 改回 `true`（默认），或调大 `enter_frames`/`finger_spread_min`。
- **CPU 占用高 / 帧率低** → 调大 `hand_every_n_frames`（如 2~3）降低手部检测频率，调试叠加层的 `HandFPS`
  会显示实际手部帧率；代价是 gate 响应变慢。
- **手控接管时仍想用眨眼点击** → 保持 `suspend_blink_while_hand: false`（默认）；若手张开时误触点击，
  改成 `true` 暂停眨眼。

## 常见问题

- **光标漂移**：重新校准；确认头部位置与校准时一致；避免光线剧烈变化。
- **眨眼误识别 / 点击误触**：调小 `close_ratio`、调大 `group_gap`；先只用 3 次以上触发动作。
- **帧率低**：降低 `camera.width/height`，用 `--no-window` 关闭界面，或关闭其他占用 CPU 的程序。
- **macOS 摄像头与辅助功能权限**：需要你在「系统设置 → 隐私与安全性」中手动为终端/Python
  授予「摄像头」与「辅助功能」权限，本程序不会代为修改系统设置。
- **Linux Wayland**：Wayland 下 `pynput` 全局热键与 `pyautogui` 可能受限，建议切换到 X11 会话。

## 已知限制

- 仅支持主显示器，多显示器未适配。
- 开发与验证环境为 Python 3.12.8（见「设计决定」）。
- `mediapipe 0.10.14` 会附带安装 `opencv-contrib-python`，运行时 `cv2` 版本可能为 4.11.x。
- 强光、逆光、口罩遮挡、快速头部运动都会降低精度。
- 眨眼动作存在 `group_gap` 的固有确认延迟（默认约 0.5 秒）。
- 头动补偿只覆盖校准阶段观测到的头姿范围；超出范围时只做提示与限幅，不做外推。
- 面部模板与几何视线的 `z` 深度来自 MediaPipe 的**相对估计**（以图像宽度为单位），不是毫米级真值；
  `eyeball_offset`、`focal_scale` 均为经验参数，只保证相对改善，不代表绝对物理精度。
- 面部模板是对「某一时刻、某一表情/发型」的冻结，长期或大幅变化后建议 `--recalibrate-face` 重做。
- 特征平滑与 One Euro 滤波会引入少量延迟，追求跟手时可适当减小平滑参数。
- 手控基于 RGB 关键点，强光、逆光、手掌朝向大角度、手被脸/头发或其他物体遮挡都会降低精度。
- 左右手标签取决于 `camera.mirror` 与 `hand_control.mirror_handedness` 两个开关是否匹配，配错会把左手
  当成右手（或反之）；程序只接受右手，左手忽略。
- 手部检测与眼控/头控同时运行会增加 CPU 占用；`hand_every_n_frames` 可降频，但会让 gate 响应变慢。
- 手控默认相对位移映射，反复朝同一方向挥手会把光标累积到屏幕边缘，需要把手移回有效范围继续。
- 眼镜标记追踪目前**只输出位姿，不控制真实光标**（阶段一）；屏幕外参标定与指向控制属阶段二，本轮只有设计。
- 单标记是平面目标，正对镜头时存在 IPPE 双解歧义：证据不足时会报 `AMBIGUOUS` 而不是给出可能翻转的位姿。
- ArUco 检测对反光、运动模糊、部分遮挡与大幅侧转敏感；标记越小、越斜，位姿噪声越大。
- `--glasses-test` 的 `stale` 姿态只是 UI 保留值，不能当成有效观测使用。
- 单标记的位姿还有一项固有尺度偏差：亚像素角点落在黑框最外侧像素中心，等效边长比实体短约 1 像素，
  因此平移/深度会比真值偏小约「1 像素 ÷ 标记像素边长」（用本轮图纸做的合成回放：约 60 px 的 30 mm
  标记在 0.5 m 处读数约 −1.4%）；真实相机还会叠加模糊与曝光影响，不要把它当成毫米级真值。
- 单标记的平移量完全依赖「纸上黑框真实边长」：若打印被缩放又没按量尺结果更新
  `glasses_tracking.marker_size_m`，平移与深度会整体按同一比例偏；程序无法知道纸上真实尺寸。
- 裁掉白边、把标记贴到高反光或带花纹的背景上，都会让 ArUco 检出率下降。

## 设计决定

1. **点击位置取序列开头的快照**，所以眨眼过程中光标不会漂移；序列进行中主循环冻结光标。
2. **暂停（F9 或 `toggle_pause` 动作）后检测器停止运行，只能用 F9 恢复，不能用眨眼恢复**，这是为了安全。
3. **校准先收集初始 EAR 基线，再采样，最后用全程数据重算最终基线**；采样阶段仅用初始基线判断睁眼。
4. **使用 Python 3.12.8 而非任务书要求的 3.10/3.11**：本机没有 3.10/3.11，且 `mediapipe==0.10.14`
   提供 `cp312` wheel，已实测可用，故在本环境采用 3.12.8 并把该偏离记录于此。
5. **镜像在摄像头读取时统一处理**，其后所有模块都使用镜像后的画面，避免左右反向。
6. **运行时只写入 `data/`**；校准文件覆盖保存前先把旧文件复制为 `data/calibration.<时间戳>.bak.json`。
7. **校准文件使用 JSON 保存训练样本，不使用 pickle**；加载时重新 fit。
8. **单次眨眼默认不触发任何动作**：自然眨眼通常是孤立的，代价是动作需要等待 `group_gap` 确认。
9. **头动补偿校准**：9 点静止校准之后再采集 5 个点的头动样本（虹膜 + 头姿 + 平移 + 尺度），与静止
   样本合并训练，回归为「特征标准化 + 可选二次项 + 岭回归」，并用交叉验证在 `ridge_alphas` 中选
   `alpha`；这样头部转动时也能保持精度。校准文件额外保存 `head_pose_range` 与静止/头动分项误差。
10. **抖动抑制分三级**：特征层小窗口中值 + EMA 平滑 → 回归 → 屏幕坐标 One Euro 滤波；再由
    `deadzone_px` 死区与注视稳定锁定（`stability_window/stability_std_px`）抑制静止抖动。
11. **头姿超范围保护**：运行时若头姿超出校准范围，调试窗口提示 `HEAD OUT OF RANGE`，并将每帧
    光标位移限幅到 `out_of_range_step_px`，避免预测外推导致光标乱飞。
12. **手控与眼控分工**：手张开手掌只负责「移动光标」，连续眨眼始终负责「点击/双击/右键/拖拽」，两条路径
    互不覆盖；手控拥有独立的 One Euro 滤波状态与死区，不与眼睛滤波器共用状态；gate 关闭时光标保持不动，
    而不是回落到眼控，避免手一放下光标就乱跳；`hand_every_n_frames` 允许帧率不足时对手部检测降频。
13. **几何检测统一用未镜像原始画面**：`Camera.read_raw()` 返回未镜像帧，`Camera.read()` 才做左右镜像；
    ArUco 检测、内参标定与 PnP 一律用原始帧，镜像只用于显示，绘制检测结果时用
    `flip_display_point()` 换算，避免把未镜像标定套到镜像画面上。
14. **眼镜追踪阶段一不接管鼠标**：只新增显式入口（`--calibrate-camera`、`--glasses-test`、
    `--write-charuco-board`），默认 `pointer_source` 与现有眼控/头控/手控/点击/热键行为一律不变；
    也不复用 `MODEL_VERSION=3` 的眼控校准文件。
15. **标定板导出必须精确到物理尺寸**：`generateImage(outSize, marginSize)` 会缩掉留白导致方格边长静默变小，
    因此改用 `marginSize=0` 精确渲染 + 板外留白写字，并在导出前实测方格像素尺寸自检。
16. **单标记图纸的尺寸唯一来源是配置**：`--write-aruco-marker` 的字典/id/黑框边长直接读
    `glasses_tracking`，把边长吸附到「每格整数像素」后，用整数 px/m 写进 PNG 物理分辨率元数据（pHYs），
    使「100% 打印」后的黑框外缘正好等于配置值（默认 30.00 mm）；图上另画 0–100 mm 参考条供用户真尺复核，
    导出前还会自检黑框像素边长、居中与可检出性。刻度线一律用 `cv2.rectangle` 绘制，因为 `cv2.line`
    的粗线会把两端各外扩半个线宽，让 100 mm 参考条静默变成约 100.4 mm（实测）。

## 隐私说明

- 所有图像处理都在本地内存中完成，**不上传、不保存任何摄像头图像**。
- 只保存校准得到的数值特征（虹膜比例、头姿角度等）与屏幕坐标，存于 `data/calibration.json`。
- 运行日志只记录动作、坐标与状态，不含图像。
- 摄像头内参标定同样**只保存数值参数与质量指标**（`data/camera_calibration.json`），
  不保存、不上传任何标定图像；`--write-charuco-board` 与 `--write-aruco-marker` 输出的都是纯图案
  （标定板 / 眼镜标记图纸），不含任何摄像头画面。
- 眼镜标记追踪的调试窗口只在内存中显示画面，不落盘任何帧。

## 变更与卸载

- 环境与变更地址表：`docs/CHANGE_MANIFEST.md`（机器可读版 `docs/change_manifest.json`）。
- 工作区外操作审计日志：`audit_logs/`，**永不删除**、只追加、带哈希链。
- 自检命令：
  - `python tools/record_env.py --verify`（登记文件、sha256、审计链是否一致，退出码 0 为通过）
  - `python tools/audit_log.py --verify-chain`（审计日志哈希链，退出码 0 为通过）
  - `python tools/record_env.py --refresh`（刷新地址表的环境概览 / 依赖清单 / 工作区外操作汇总）
- 完整卸载：删除 `.venv/`、`.tmp/`、`data/` 与源码（`eyemouse/`、`tests/`、`tools/`、`docs/`、
  `main.py`、`config.yaml`、`requirements.txt`、`README.md`），**务必保留 `audit_logs/`**。
  具体命令见 `docs/CHANGE_MANIFEST.md` 的「一键卸载步骤」；这些命令只写进文档，由你手动执行。
