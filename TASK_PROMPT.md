# 任务：开发"用眼睛代替鼠标"的桌面程序（EyeMouse）

你是一名资深 Python 工程师。请在当前目录（以下称"工作区"，即项目根目录）下**一次性完成**下面描述的完整项目：写出全部代码、依赖文件、README、地址表与审计日志工具，并自行运行测试。
**不要向我提问**。遇到不确定的地方，按本文默认值决定，并把决定写进 README 的「设计决定」一节。
**请严格按第 12 节「开发步骤」的顺序工作，每完成一步先自检、登记地址表，再进入下一步。**

---

## 0. 最高优先级红线（任何情况下都不得违反，优先级高于本文其他所有内容）

1. **工作区之外的文件，除"安装依赖"这一例外，禁止做任何删除操作。**
   - "删除"包括但不限于：`rm`、`del`、`rmdir`、`Remove-Item`、`os.remove`、`os.unlink`、`os.rmdir`、`shutil.rmtree`、`Path.unlink`、清空文件内容、覆盖为空、移动到回收站、针对工作区外环境的 `pip uninstall`、`pip cache purge` 等。
   - "安装依赖"例外的唯一含义是：`pip install` 过程中，pip 自身对其缓存或临时文件所做的内部处理。你**不得**主动删除任何工作区之外的文件，也不得借"安装依赖"之名清理其他文件。
2. **对工作区之外的任何文件或系统状态的每一次修改（新建、写入、追加、重命名、移动、改权限、改配置、改环境变量等），都必须留存审计日志。**
   - 必须遵循"**先写日志，后执行，再回写结果**"：执行前先追加一条 `PLANNED` 记录；执行后追加一条 `DONE` 或 `FAILED` 记录。
   - 默认策略是**根本不做**这类修改。只有无法避免时才做，且必须写日志。
3. **审计日志永不删除。**
   - 所有审计日志统一存放在**一个文件夹**：`<工作区>/audit_logs/`。
   - 日志文件只允许"追加写入"（以 `'a'` 模式打开）。禁止删除、截断、覆盖、重命名、移动、重写、编辑历史行。
   - 任何清理、卸载、重置、重新生成步骤，都**不得**触碰 `audit_logs/`。
4. **工作区之内的删除**（例如重建 `.venv`、清理 `__pycache__`）允许，但必须通过 `tools/safe_delete.py` 执行，并登记到地址表。绝对不允许删除 `audit_logs/`。
5. 如发现自己即将违反以上任一条，**立即停止该操作**，改用更安全的方案，并把此事记入审计日志（`phase=BLOCKED`）。

---

## 1. 项目目标

用普通笔记本或 USB 摄像头（RGB，无红外）追踪用户视线，实现：
1. 视线控制屏幕鼠标光标移动；
2. 通过**连续眨眼的不同次数**触发不同鼠标动作（左键、右键、双击、拖拽等），另保留"注视停留点击"作为可选模式；
3. 9 点校准流程，校准结果可保存和复用；
4. 安全机制：用户任何时候都能夺回鼠标控制权；
5. 「环境与变更地址表」：随时能看到项目放了哪些文件、装了哪些依赖、在什么绝对路径、改了什么、怎么撤销；
6. 「工作区外操作审计日志」：对工作区之外的任何修改都有不可删除的记录。

目标精度：校准后光标落点与注视点平均误差 ≤ 150 像素（1080p 屏，约 60cm 观看距离）。
目标帧率：≥ 25 FPS（CPU 运行）。

---

## 2. 技术栈与环境（必须遵守）

- Python 3.10 或 3.11（**不要用 3.12+**，mediapipe 兼容性问题）。
- 依赖版本固定写入 `requirements.txt`：
  ```
  mediapipe==0.10.14
  opencv-python==4.9.0.80
  numpy<2
  scikit-learn>=1.3
  pyautogui>=0.9.54
  pynput>=1.7.6
  PyYAML>=6.0
  pytest>=7.0
  ```
- 人脸关键点使用 `mediapipe.solutions.face_mesh.FaceMesh`，参数 `max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5`。
- 鼠标使用 `pyautogui`，设置 `pyautogui.PAUSE = 0`、`pyautogui.FAILSAFE = False`（我们自己实现更完善的安全机制）。
- 全局热键使用 `pynput.keyboard.Listener`（独立线程运行，线程安全地修改状态）。
- Windows 下程序启动时调用 `ctypes.windll.shcore.SetProcessDpiAwareness(2)`（try/except 包裹，非 Windows 跳过），避免分辨率获取错误。
- 屏幕尺寸用 `pyautogui.size()` 获取。仅支持主显示器，多显示器写入 README「已知限制」。
- 代码必须跨平台可导入（Windows/macOS/Linux），平台相关代码要做判断。
- 所有代码加类型注解和简明中文注释；每个模块顶部有一句话说明用途。

### 2.1 环境隔离规则（强制）
1. **必须使用项目内虚拟环境 `./.venv`**，禁止 `pip install` 到全局或用户目录。若检测到当前不在虚拟环境中，先创建并激活 `.venv`（`python -m venv .venv`），之后所有 pip 与 python 命令都通过 `.venv` 内的解释器执行。
2. 为尽量避免 pip 在工作区之外写入缓存，安装依赖时使用 `pip install --no-cache-dir -r requirements.txt`，并把 pip 的临时目录指向工作区内（仅在当前命令的子进程环境中设置 `TMPDIR`/`TEMP`/`TMP` 为 `<工作区>/.tmp/`，**不得**修改系统或用户级环境变量）。`.tmp/` 属于工作区内目录，可通过 `tools/safe_delete.py` 清理。
3. **禁止修改系统级设置**：不改系统/用户环境变量、不改注册表、不改系统 PATH、不安装系统服务或开机启动项。
   如确实必须（例如 macOS 需要用户手动授权摄像头和辅助功能），**只在 README 与地址表中提示用户手动操作，不要代为执行**。
4. 程序**运行期间**只允许写入 `./data/` 目录（校准文件、运行日志），不得写入其他位置。
5. 开发期间，每次创建、修改、删除文件，或执行会改变环境的命令（创建虚拟环境、pip install 等），都必须**立即**登记到地址表（见第 6 节）。不允许最后一次性补写。

### 2.2 工作区外操作与审计日志规则（强制，对应第 0 节红线）

**A. 判定"工作区外"**：任何经 `os.path.realpath` 解析后，不位于工作区（项目根目录）之内的路径，都算工作区外（注意符号链接和 `..` 逃逸）。

**B. 允许与禁止一览**

| 操作 | 工作区内 | 工作区外 |
|---|---|---|
| 读取 | 允许 | 允许（读取不需要日志；但不得把读取到的敏感内容写入日志或地址表） |
| 新建/写入/追加 | 允许（登记地址表） | 默认不做；确需做必须先写审计日志 |
| 修改（重命名、移动、改权限、改配置） | 允许（登记地址表） | 默认不做；确需做必须先写审计日志 |
| 删除 | 仅通过 `tools/safe_delete.py`，登记地址表 | **一律禁止**（唯一例外：pip 安装依赖过程中的内部处理） |
| 删除/修改 `audit_logs/` 中任何内容 | **一律禁止** | **一律禁止** |

**C. 审计日志位置与格式**
- 唯一文件夹：`<工作区>/audit_logs/`。
- 文件命名：`audit_YYYYMMDD.jsonl`（按天分文件，每行一条 JSON）。只追加。
- 每条记录字段：
  ```
  seq            当天序号（从 1 递增）
  ts             本地时间 ISO 格式
  phase          PLANNED | DONE | FAILED | BLOCKED
  op             操作类型：create | write | append | rename | move | chmod | config | pip_install | other
  target         被操作对象的绝对路径（realpath）
  reason         为什么必须这样做
  command        实际执行的命令或函数调用的字符串描述
  result         结果描述（PLANNED 时为空）
  ref_seq        DONE/FAILED/BLOCKED 对应的 PLANNED 的 seq（可空）
  prev_hash      上一条记录的 hash（当天第一条取前一个日志文件最后一条的 hash，没有则为 64 个 0）
  hash           sha256(prev_hash + 本条除 hash 外所有字段的规范化 JSON，键排序、无多余空白)
  ```
- 哈希链用于发现篡改，不是为了加密。

**D. 工具（只用标准库）**
- `tools/audit_log.py`：
  - 函数 `log(phase, op, target, reason, command, result="", ref_seq=None, root=None) -> dict`：追加一条记录并返回；自动创建 `audit_logs/`；以 `'a'` 模式写入，每次写完 `flush` + `os.fsync`。
  - 函数 `guard_outside_write(target, op, reason, command, root=None) -> int`：写 `PLANNED` 并返回 `seq`；调用方在执行完成后调用 `log("DONE"/"FAILED", ..., ref_seq=seq)`。
  - 函数 `is_outside_workspace(path, root=None) -> bool`。
  - `root` 参数默认由本文件所在位置推断出工作区；**所有工具函数（含 `log_change`、`safe_delete`、`record_env`）都必须支持显式传入 `root`，测试只能使用临时目录作为 `root`，不得写入真实的 `audit_logs/` 和真实地址表**。
  - 命令行：`python tools/audit_log.py --verify-chain`（校验所有日志文件的哈希链，有断裂则退出码 1）；`--show [--date YYYYMMDD]`（只读展示）；`--log ...`（手动追加一条）。
  - **不得提供任何删除、清空、重写日志的函数或命令行选项。**
- `tools/safe_delete.py`：
  - 函数 `safe_delete(path, root=None)`：
    1. `realpath` 解析；
    2. 若在工作区之外 → 拒绝，抛 `PermissionError`，并写一条 `BLOCKED` 审计记录；
    3. 若位于 `audit_logs/` 之内或就是 `audit_logs/` → 拒绝，写 `BLOCKED` 记录；
    4. 若就是工作区根目录本身 → 拒绝；
    5. 否则执行删除，并调用 `log_change.py` 登记到地址表（类型 `删除文件`）。
  - 项目内任何代码、脚本、命令，凡需删除文件，**都必须调用它**；不得直接使用 `os.remove`/`shutil.rmtree` 等（`tools/safe_delete.py` 自身除外）。
- 项目自身代码（`eyemouse/` 包）运行时不应有任何工作区外的写操作；如有，必须调用 `guard_outside_write`。

**E. 执行任何 shell 命令前的自检清单（每次都要过一遍）**
1. 这条命令会不会写/改/删工作区之外的文件？
2. 如果会：能否改写成只在工作区内操作？能 → 改写；不能 → 先写 PLANNED 日志再执行，执行完写 DONE/FAILED。
3. 涉及删除且在工作区外？→ 一律不执行，写 BLOCKED 日志，改用其他方案。
4. 是否会碰到 `audit_logs/`？→ 若会，不执行。

---

## 3. 项目结构（必须完全按此创建）

```
eyemouse/                        # 项目根目录 = 工作区
├── README.md
├── requirements.txt
├── config.yaml                  # 默认配置
├── main.py                      # 入口
├── eyemouse/
│   ├── __init__.py
│   ├── config.py                # 读取/校验配置，dataclass
│   ├── camera.py                # 摄像头封装
│   ├── landmarks.py             # MediaPipe 封装 + 关键点索引常量
│   ├── features.py              # 特征提取（虹膜比例、头姿、EAR）
│   ├── head_pose.py             # solvePnP 头部姿态
│   ├── filters.py               # One Euro Filter
│   ├── calibration.py           # 校准流程 + 回归模型 + 保存加载 + 眨眼练习
│   ├── click_detector.py        # 连续眨眼计数状态机 + 停留点击
│   ├── mouse.py                 # 鼠标控制封装（可 mock）
│   ├── hotkeys.py               # 全局热键
│   ├── app.py                   # 主循环，状态机整合
│   └── ui.py                    # OpenCV 绘制：校准界面、调试叠加层
├── tools/
│   ├── log_change.py            # 追加变更记录到地址表
│   ├── record_env.py            # 生成/刷新环境概览与依赖清单，自检
│   ├── audit_log.py             # 工作区外操作审计日志（只追加，哈希链）
│   └── safe_delete.py           # 带保护的删除（拒绝工作区外与 audit_logs）
├── docs/
│   ├── CHANGE_MANIFEST.md       # 环境与变更地址表（人读）
│   └── change_manifest.json     # 同内容机器可读版
├── audit_logs/                  # 审计日志唯一目录，永不删除
│   └── audit_YYYYMMDD.jsonl
├── tests/
│   ├── test_filters.py
│   ├── test_click_detector.py
│   ├── test_features.py
│   ├── test_calibration.py
│   ├── test_config.py
│   ├── test_tools.py
│   └── test_audit.py
├── data/                        # 运行时生成：calibration.json、run.log
├── .tmp/                        # pip 等临时目录（工作区内，可通过 safe_delete 清理）
└── .venv/                       # 项目内虚拟环境
```

## 4. 各模块详细规格

### 4.1 config.yaml 与 config.py
用 `dataclass` 定义配置，缺失字段使用默认值，非法值抛出带中文说明的 `ValueError`。默认值（`config.yaml` 必须写全）：

```yaml
camera:
  index: 0
  width: 1280
  height: 720
  fps: 30
  mirror: true                # 画面左右镜像（符合直觉）
tracking:
  min_cutoff: 1.0             # One Euro Filter
  beta: 0.02
  d_cutoff: 1.0
  lost_face_timeout: 0.5      # 秒，丢失人脸超过该时间则暂停移动光标
  deadzone_px: 3              # 与上次光标位置距离小于该值则不移动
click:
  mode: "blink_sequence"      # blink_sequence | dwell | both | none
  close_ratio: 0.60           # EAR < 基线*0.60 判定为"闭眼"
  open_ratio: 0.75            # EAR > 基线*0.75 判定为"睁眼"（迟滞，防抖）
  blink_min_duration: 0.06    # 闭眼短于该值视为噪声，忽略
  blink_max_duration: 0.50    # 闭眼长于该值：视为"非有意眨眼"，丢弃整个序列
  group_gap: 0.50             # 两次眨眼的睁眼间隔 <= 该值则属于同一组；超过则结算
  max_blinks: 6               # 超过此次数的序列忽略
  freeze_lookback: 0.30       # 点击位置快照：取"序列第一次闭眼开始前 0.3 秒"的光标位置
  cooldown: 0.6               # 动作执行后的最小间隔
  actions:                    # 键=连续次数，值=动作名
    1: "none"
    2: "left_click"
    3: "right_click"
    4: "double_click"
    5: "toggle_drag"
    6: "none"
  dwell_time: 1.2             # 注视停留触发时间（秒）
  dwell_radius: 40            # 像素，停留判定半径
calibration:
  grid: 3                     # 3x3 = 9 点
  margin: 0.08                # 校准点距屏幕边缘的比例
  settle_time: 1.0            # 每点先等待用户找到点
  sample_time: 1.5            # 然后采样时长
  poly_degree: 2
  ridge_alpha: 1.0
  file: "data/calibration.json"
  practice_blinks: true       # 校准后是否进入眨眼练习
safety:
  pause_key: "f9"             # 暂停/恢复
  quit_key: "f10"             # 退出
  recalibrate_key: "f8"       # 重新校准
  toggle_click_key: "f7"      # 开关点击功能
  cycle_mode_key: "f6"        # 循环切换 click.mode
debug:
  show_window: true           # 显示摄像头小窗与叠加层
  log_level: "INFO"
  log_file: "data/run.log"
```

**配置校验规则**：
- `actions` 的键必须是 1 ~ `max_blinks` 的整数；
- 合法动作名：`none, left_click, right_click, double_click, middle_click, toggle_drag, toggle_pause`，其他值抛中文 `ValueError`；
- 必须满足 `close_ratio < open_ratio`；
- 必须满足 `blink_min_duration < blink_max_duration`；
- `mode` 只能是 `blink_sequence | dwell | both | none`；
- 各时间、比例、像素数值必须为正数；
- `calibration.file` 与 `debug.log_file` 解析后必须位于工作区的 `data/` 目录内，否则抛中文 `ValueError`（防止运行时写到工作区外）。

### 4.2 camera.py
- 类 `Camera`：`open()`, `read() -> Optional[np.ndarray]`, `release()`，支持 `with` 上下文。
- 打开失败抛出带中文提示的异常（"无法打开摄像头 index=X，请检查是否被占用或权限"）。
- 根据 `config.camera.mirror` 决定是否 `cv2.flip(frame, 1)`。**镜像必须在最开始统一处理**，其后所有模块都用镜像后的画面，避免左右反向。

### 4.3 landmarks.py
- 常量（MediaPipe FaceMesh 索引，按**图像左右**命名，虹膜与眼角配对必须一致）：
  ```
  # 图像左侧的眼睛（A）
  EYE_A_OUTER=33, EYE_A_INNER=133, EYE_A_UP=159, EYE_A_DOWN=145, IRIS_A_CENTER=468
  # 图像右侧的眼睛（B）
  EYE_B_INNER=362, EYE_B_OUTER=263, EYE_B_UP=386, EYE_B_DOWN=374, IRIS_B_CENTER=473
  # EAR 用的 6 点（顺序 p1..p6，p1/p4 为眼角，p2/p3 上眼睑，p5/p6 下眼睑）
  EYE_A_EAR = [33, 160, 158, 133, 153, 144]
  EYE_B_EAR = [362, 385, 387, 263, 373, 380]
  # 头姿 solvePnP 用 6 点
  NOSE_TIP=1, CHIN=152, MOUTH_A=61, MOUTH_B=291
  # 头姿用到的眼角外侧点直接复用 EYE_A_OUTER=33 与 EYE_B_OUTER=263
  ```
- 类 `LandmarkDetector`：`detect(frame_bgr) -> Optional[FaceLandmarks]`。
  `FaceLandmarks` 是 dataclass，含：`pts_norm (478,2)`（归一化坐标）、`pts_px (478,2)`（像素坐标）、`pts_3d (478,3)`（归一化 xyz）、`img_w`, `img_h`。
- 提供 `close()` 释放资源。

### 4.4 head_pose.py
- 函数 `estimate_head_pose(face: FaceLandmarks) -> tuple[float, float, float]`，返回 `(yaw, pitch, roll)`（度）。
- 使用 `cv2.solvePnP`，通用 3D 人脸模型点（单位 mm，顺序与 2D 点对应）：
  ```
  鼻尖      (0, 0, 0)
  下巴      (0, -63.6, -12.5)
  眼角A外侧 (-43.3, 32.7, -26)
  眼角B外侧 (43.3, 32.7, -26)
  嘴角A     (-28.9, -28.9, -24.1)
  嘴角B     (28.9, -28.9, -24.1)
  ```
  相机内参近似：`focal = img_w`，主点为图像中心，无畸变。
- 用 `cv2.Rodrigues` + `cv2.RQDecomp3x3` 得到欧拉角，并把角度归一到 [-90, 90]。solvePnP 失败返回 `(0.0, 0.0, 0.0)` 并记录 warning。

### 4.5 features.py
- `compute_ear(face) -> tuple[float, float]`：左右眼 EAR，公式 `(|p2-p6| + |p3-p5|) / (2*|p1-p4|)`，用像素坐标，分母加 `1e-6`。
- `compute_iris_ratio(face) -> np.ndarray`：对每只眼计算
  - `x_ratio`：虹膜中心在水平眼角连线上的投影比例（0~1）；
  - `y_ratio`：虹膜中心 y 在上下眼睑之间的位置比例；
  返回 `[xA, yA, xB, yB]`。分母加 `1e-6` 防止除零。
  注意：A 眼取向量 33→133（outer→inner），B 眼取向量 362→263（inner→outer），两只眼的 x_ratio 都表示"从图像左向图像右"的比例，语义一致，并在代码注释说明。
- `build_feature_vector(face) -> Optional[np.ndarray]`：拼接
  `[xA, yA, xB, yB, mean_x, mean_y, yaw/45, pitch/45, roll/45, nose_x_norm, nose_y_norm]`，共 11 维。`mean_x/mean_y` 是双眼平均值。
- 所有特征值必须 `np.isfinite`，否则返回 `None`。

### 4.6 filters.py
- 标准 **One Euro Filter**（Casiez et al. 2012），类 `OneEuroFilter(min_cutoff, beta, d_cutoff)`，方法 `__call__(x: float, t: float) -> float`。
- `OneEuroFilter2D`，对 (x, y) 分别滤波。
- 支持 `reset()`。时间戳 `t` 由调用者传入（便于单元测试）。首次调用直接返回输入值；`t` 未前进（dt≤0）时返回上次输出。
### 4.7 calibration.py
- 类 `Calibrator`：
  - `run(camera, detector, cfg, ui) -> CalibrationModel`：
    1. **初始基线阶段**：校准点出现之前，先用 1.5 秒收集初始 EAR（界面提示 "Look at the screen, keep eyes open"），取 **80 分位数**作为"初始睁眼基线"。人脸无效的帧不计入；有效帧少于 10 帧则重试一次，再失败则报错并允许 ESC 取消。
    2. **采样阶段**：全屏依次显示 9 个点（3×3，含 margin）。每点：先显示 `settle_time` 秒（点带收缩动画提示用户注视），再采样 `sample_time` 秒；仅在睁眼（EAR 高于**初始基线**的 0.7）且人脸有效时采样。**每点至少需要 10 个有效样本，否则该点重采一次；再失败则报错，并允许 ESC 取消。**
    3. **最终基线**：校准全程（含初始基线阶段）持续收集 EAR，结束后重新取 **80 分位数**作为"最终睁眼 EAR 基线"，保存到模型里，供点击检测使用。采样阶段的判断始终使用初始基线，不使用最终基线。
  - 每点样本保留全部原始样本用于训练；同时计算**中位数特征**用于评估显示。
  - **眨眼练习**（`cfg.calibration.practice_blinks` 为 true 时，校准点完成后进入，ESC 可跳过）：
    界面依次提示 "Blink 2 times"、"Blink 3 times"、"Blink 4 times"（界面文字为英文），使用 `ClickDetector`（基线用最终基线）实时识别，显示识别到的次数与对应动作名，让用户熟悉节奏。**练习期间不触发任何真实鼠标动作。**
- 类 `CalibrationModel`：
  - 模型：`Pipeline(StandardScaler, PolynomialFeatures(degree), Ridge(alpha))`，多输出（x、y）。
  - `predict(features) -> (x_px, y_px)`，结果 clip 到屏幕范围。
  - `evaluate()`：**留一点交叉验证**（每次留出一个校准点的全部样本）计算平均误差（px），校准结束后显示在界面上并写日志。若平均误差 > 250px，提示"校准质量较差，建议重新校准（保持头部稳定、光线充足）"。
  - `save(path)` / `load(path)`：**使用 JSON，不使用 pickle**。保存训练样本 X、Y、最终 EAR 基线、屏幕尺寸、poly_degree、ridge_alpha；加载时重新 fit。加载时若屏幕尺寸与保存时不同，抛出/返回明确提示并要求重新校准。
  - `save` 只允许写入工作区的 `data/` 目录；保存后日志打印校准文件的**绝对路径**。覆盖已有校准文件前，先把旧文件复制为 `data/calibration.<时间戳>.bak.json`（不删除旧文件，仅在工作区内）。

### 4.8 click_detector.py（连续眨眼计数，纯逻辑）
**不依赖摄像头和鼠标。**

#### 4.8.1 事件与接口
```python
@dataclass
class ClickEvent:
    action: str                  # 见合法动作名
    blink_count: int
    position: tuple[float, float]

class ClickDetector:
    def __init__(self, cfg: ClickConfig): ...
    def update(self, t: float, avg_ear: float, ear_baseline: float,
               gaze_xy: tuple[float, float], face_ok: bool) -> Optional[ClickEvent]: ...
    def push_position(self, t: float, x: float, y: float) -> None: ...
    def in_sequence(self) -> bool: ...      # 序列进行中（CLOSED 或 blink_count>0）
    def pending_count(self) -> int: ...     # 当前已累计眨眼次数
    def settle_remaining(self) -> float: ...# 距离结算还剩多少秒（0~group_gap），供 UI 倒计时条
    def dwell_progress(self) -> float: ...  # 0~1，停留进度
    def set_mode(self, mode: str) -> None: ...
    def reset(self) -> None: ...
```

#### 4.8.2 眨眼序列规则（必须按此实现）
内部状态：`OPEN` / `CLOSED`，外加当前序列数据：`blink_count`、`first_close_time`、`last_open_time`、`close_start`、`snapshot_pos`（序列的点击位置快照，初始为空）。

1. **迟滞**：`OPEN` 状态下 `avg_ear < 基线×close_ratio` → 进入 `CLOSED`，记录 `close_start`；`CLOSED` 状态下 `avg_ear > 基线×open_ratio` → 回到 `OPEN`，得到闭眼时长 `d = t - close_start`。介于两阈值之间时保持原状态。
2. **位置快照**（进入 `CLOSED` 的瞬间执行，仅当 `blink_count == 0`，即这是序列的第一次闭眼）：
   - 检测器内部维护最近 **2 秒**的 `(t, x, y)` 光标历史（由 `push_position` 写入，超过 2 秒的记录丢弃）。
   - 取历史中满足 `t_hist <= close_start - freeze_lookback` 的**最近一条**，保存为 `snapshot_pos`；
   - 若没有满足条件的记录，取历史中最早一条；历史为空则用当前 `gaze_xy`。
   - 快照随序列存活。序列中后续的闭眼不再重新取快照。
3. 回到 OPEN 时按 `d` 判断：
   - `d < blink_min_duration`：噪声，忽略（不计数，不影响已有序列）。若此时 `blink_count == 0`（噪声发生在序列开头），同时丢弃刚取的 `snapshot_pos`。噪声结束后，若 `blink_count == 0`，检测器回到"无序列"状态，`in_sequence()` 返回 False；
   - `blink_min_duration <= d <= blink_max_duration`：有效眨眼，`blink_count += 1`，`last_open_time = t`；若这是序列第一次眨眼，记录 `first_close_time = close_start`；
   - `d > blink_max_duration`：视为有意休息或非指令，**清空当前序列（含快照），不触发任何动作**。
4. **结算**：处于 `OPEN` 且 `blink_count > 0` 且 `t - last_open_time > group_gap` → 序列结束：
   - 若 `1 <= blink_count <= max_blinks` 且 `actions.get(blink_count, "none") != "none"` 且冷却已过 → 返回 `ClickEvent`，其 `position` **直接使用 `snapshot_pos`**，不再回查历史；
   - `blink_count > max_blinks` → 不触发；
   - 无论是否触发，都清空序列（含快照）。
5. `face_ok=False`：立即清空序列（含快照）并回到 OPEN，不触发任何事件，同时重置停留计时。
6. 序列进行中时 `in_sequence()` 返回 True，主循环据此**冻结光标**。冻结期间主循环不再调用 `push_position`，这不影响快照，因为快照已在序列开头取得。
7. 冷却：执行任何动作后 `cooldown` 秒内产生的事件丢弃（但序列仍照常清空）。
8. 动作 `toggle_drag` 由 `app.py` 维护 `dragging` 标志（检测器只返回事件）；`toggle_pause` 等价于按暂停键。暂停后检测器停止运行，**只能用 F9 恢复**，不能用眨眼恢复。
9. 模式控制：`mode` 为 `blink_sequence` 或 `both` 时启用眨眼序列；为 `dwell` 或 `both` 时启用停留；`none` 时 `update` 始终返回 None。

#### 4.8.3 停留点击
- 注视点在 `dwell_radius` 内持续 `dwell_time` 秒触发 `left_click`（`blink_count=0`）；
- 触发后必须移出半径才能再次触发；
- `face_ok=False` 时重置计时；
- 眨眼序列进行中不累计停留时间；
- `mode=both` 时两者都启用。

### 4.9 mouse.py
- 抽象类 `MouseController`，方法：`move(x, y)`、`click(button="left")`、`double_click()`、`press(button="left")`、`release(button="left")`。
- `PyAutoGuiMouse`：使用 `pyautogui.moveTo / click / doubleClick / mouseDown / mouseUp`，所有调用 try/except 包裹，异常记录日志但不崩溃。
- `DryRunMouse`：每个方法只打印日志，用于无桌面环境和单元测试。
- 命令行 `--dry-run` 使用后者。

### 4.10 hotkeys.py
- 类 `HotkeyManager`：注册
  - F9：暂停/恢复
  - F10：退出
  - F8：重新校准
  - F7：开关点击功能
  - F6：循环切换 `click.mode`（blink_sequence → dwell → both → none → blink_sequence）
- 用 `threading.Event` / 线程安全标志位与主循环通信，主循环通过 `poll()` 读取并清除请求。
- 暂停状态下：程序**完全不移动鼠标**，只在调试窗口显示 `PAUSED`。
- F9 暂停时清空眨眼序列并释放拖拽（若正在拖拽）。

### 4.11 ui.py
使用 OpenCV 绘制：
- **校准界面**：全屏黑底，绿色/红色圆点 + 收缩动画，顶部提示文字，右上角进度 n/9。
- **眨眼练习界面**：显示要求的次数、已识别次数、对应动作名，ESC 跳过。
- **调试窗口**：缩小的摄像头画面 + 虹膜/眼角关键点 + 当前 EAR 值 + FPS + 状态文字（TRACKING / PAUSED / NO FACE / CALIBRATING）+ 停留进度圈 + 当前点击模式 + 热键提示。另外：
  - 实时显示 `Blinks: N`（当前序列累计次数）与倒计时条（距离结算还剩多少 `group_gap`）；
  - 触发动作后显示动作名（如 `LEFT CLICK`、`RIGHT CLICK`、`DOUBLE CLICK`）0.8 秒；
  - 拖拽中显示 `DRAGGING`。
- OpenCV 无法直接显示中文，**调试叠加层和校准提示统一使用英文**，避免乱码；中文说明放在终端日志和 README。
- 调试窗口为置顶小窗，默认位置在屏幕右下角，**不能遮挡校准界面**（校准时关闭或隐藏调试窗口）。

### 4.12 app.py（主循环）
状态机：`INIT → CALIBRATING → TRACKING ⇄ PAUSED → EXIT`。

1. **启动**：加载配置；初始化日志（同时输出终端和 `data/run.log`，以追加模式写入，不删除旧日志）；打印并写入一次：项目根绝对路径、配置文件绝对路径、校准文件绝对路径、日志文件绝对路径、审计日志目录绝对路径、Python 解释器绝对路径、是否处于虚拟环境。若存在有效 `calibration.json` 且屏幕尺寸匹配，直接加载并进入 TRACKING；否则进入 CALIBRATING。`--recalibrate` 强制重新校准。若校准文件被新建或覆盖，提示其绝对路径。
2. **TRACKING 每帧**：
   - 读帧 → 检测关键点 → 若无人脸：记录 `last_seen`，超过 `lost_face_timeout` 则显示 NO FACE 并**不再移动光标**，同时 `detector.update(face_ok=False)`；
   - 提取特征 → 模型预测屏幕坐标 → One Euro 滤波 → 死区处理 → `mouse.move`；
   - **冻结光标**：`detector.in_sequence()` 为 True，或 EAR 低于闭眼阈值（基线 × close_ratio）时，不更新光标位置；
   - 每帧调用 `detector.push_position(t, x, y)`（只在光标未冻结时推送）；
   - 调用 `detector.update(...)`，处理返回的 `ClickEvent`：
     - `left_click` / `right_click` / `middle_click`：先 `mouse.move(event.position)`，再 `mouse.click(button)`；
     - `double_click`：先移动到 `event.position`，再 `mouse.double_click()`；
     - `toggle_drag`：先移动到 `event.position`；若 `dragging=False` → `mouse.press("left")` 并置 True；否则 `mouse.release("left")` 并置 False；
     - `toggle_pause`：等价于 F9；
     - 动作执行后在 UI 显示动作名 0.8 秒，日志记录动作、次数、坐标。
3. **拖拽安全**：进入暂停、丢失人脸超时、退出、异常、重新校准前，若 `dragging=True`，必须先 `mouse.release("left")`。
4. 任何未捕获异常：记录日志、释放拖拽、释放摄像头、退出，不能让程序卡死鼠标。
5. `try/finally` 保证摄像头和 MediaPipe 被释放。
6. 帧循环统计 FPS（滑动平均），低于 15 FPS 时日志打 warning。
7. 处理热键请求（暂停、退出、重新校准、开关点击、切换模式），切换模式后调用 `detector.set_mode()` 并在调试窗口显示当前模式。
8. 程序运行期间**只写入 `data/`**，不得写入工作区外任何位置；不得删除任何文件。

### 4.13 main.py
命令行参数（`argparse`）：
```
--config PATH        配置文件，默认 config.yaml
--recalibrate        强制重新校准
--dry-run            不真正控制鼠标
--no-window          不显示调试窗口
--camera-test        仅打开摄像头并显示关键点，不控制鼠标（用于排错）
--log-level LEVEL
```
无摄像头时 `--camera-test` 必须给出友好的中文错误，而不是堆栈。启动时在终端打印热键说明。

---

## 5. 连续眨眼交互说明（默认映射，可通过 config 改）

| 连续眨眼次数 | 动作 |
|---|---|
| 1 次 | 无（视为自然眨眼） |
| 2 次 | 左键单击 |
| 3 次 | 右键单击 |
| 4 次 | 左键双击 |
| 5 次 | 开始/结束拖拽（按下/释放左键） |
| ≥6 次 | 忽略 |

设计原因（写入 README）：自然眨眼是孤立的（约 0.1~0.4 秒一次），有意的连续眨眼间隔很短，所以单次眨眼默认不触发任何动作。代价是延迟：最后一次眨眼后要等 `group_gap`（默认 0.5 秒）确认没有下一次眨眼，才执行动作。


## 6. 环境与变更「地址表」（强制）

目的：让我随时知道，这个项目在我电脑上**放了哪些文件、装了哪些依赖、它们在哪个绝对路径、改了什么系统设置、如何撤销**。

### 6.1 地址表文件
创建 `docs/CHANGE_MANIFEST.md`，同时维护机器可读版 `docs/change_manifest.json`。变更记录表头固定为：

```
| 序号 | 时间(本地) | 类型 | 绝对路径 | 说明/目的 | 回滚方式 |
```
- 「类型」取值：`新建文件 / 修改文件 / 删除文件 / 创建目录 / 安装依赖 / 运行命令 / 工作区外修改 / 系统设置(应为空)`。
- 「绝对路径」必须是真实绝对路径（用 `os.path.abspath` 得到），不要写相对路径。
- 「回滚方式」写清楚，例如 `删除该文件`、`在 .venv 内 pip uninstall xxx`、`删除 .venv 目录`。其中 `pip uninstall` 只能针对项目 `.venv`。
- 凡类型为「工作区外修改」的条目，必须在「说明/目的」里写上对应的审计日志 `seq` 与日志文件名。
- 文件末尾固定包含以下小节（顺序固定，标题固定）：
  1. **环境概览**：操作系统及版本、Python 解释器绝对路径与版本、虚拟环境绝对路径、项目根目录（工作区）绝对路径、审计日志目录绝对路径。
  2. **依赖清单**：每个包的 名称 / 版本 / 安装位置（site-packages 内的绝对路径）/ 用途 / 是否在 requirements.txt。
  3. **运行时会写入的位置**：只应有 `<项目>/data/calibration.json`、`<项目>/data/calibration.*.bak.json`、`<项目>/data/run.log`。
  4. **工作区外操作汇总**：列出审计日志中所有 `phase=DONE/FAILED/BLOCKED` 的工作区外操作摘要（时间、对象、结果）与审计日志目录路径；若无则写「无」。
  5. **系统级改动**：明确写「无」；若有则逐条列出（应当没有）。
  6. **一键卸载步骤**：按 Windows / macOS / Linux 分别给出完整命令。**卸载时必须保留 `audit_logs/`**：删除 `.venv/`、`.tmp/`、`data/` 与源码，保留 `audit_logs/`；或先把 `audit_logs/` 复制到用户指定的安全位置再处理项目目录。卸载步骤中不得出现删除 `audit_logs/` 的命令。这些命令只写进文档，由用户手动执行；Codex 在开发过程中不得执行它们。

### 6.2 tools/log_change.py
- 命令行：`python tools/log_change.py --type 新建文件 --path <路径> --note "说明" --rollback "回滚方式" [--audit-seq N]`。
- 函数接口支持 `root` 参数（测试用临时目录）。
- 自动补全时间、序号，把相对路径转成绝对路径，同时写入 md 和 json。
- 若 `--path` 在工作区之外，类型必须为「工作区外修改」，且必须提供 `--audit-seq`，否则拒绝写入并报错。
- 文件已存在则追加，不覆盖历史；变更表位于固定小节之前，追加时不得破坏固定小节。
- 登记「新建文件 / 修改文件」时记录该文件当前 sha256 到 json；同一文件再次登记时更新其最新 sha256。
- 只使用标准库。

### 6.3 tools/record_env.py
- 用 `sys.executable`、`sys.prefix`、`platform`、`importlib.metadata` 收集环境信息与每个依赖的版本、安装位置（`distribution.locate_file('')`）。
- 检查当前是否在项目 `.venv` 内，不在则打印醒目警告。
- `--refresh`：刷新地址表中「环境概览」「依赖清单」「工作区外操作汇总」三节（后者只读 `audit_logs/`）。
- `--verify`：
  - 遍历 json 中登记的「新建文件 / 修改文件」，检查文件是否存在，并对源码文件计算 sha256 与登记值对比；
  - 列出「未登记的新文件」和「已登记但缺失的文件」；
  - 忽略 `.venv/`、`.tmp/`、`__pycache__/`、`.pytest_cache/`、`data/`、`audit_logs/`；
  - 顺带校验 `audit_logs/` 的哈希链（只读）；
  - 有任何偏差退出码为 1，否则为 0。
- 所有函数支持 `root` 参数；只使用标准库，不得新增依赖。

### 6.4 登记时机
- 第 12 节每个开发步骤完成后，运行 `python tools/log_change.py ...`（该步骤创建或修改的每个文件各登记一条，可写脚本循环）。
- 创建 `.venv`、pip install 也要登记（类型 `创建目录` / `安装依赖`）。
- 编写 README 前运行 `record_env.py --refresh` 与 `--verify`；README 写完后再登记并再次 `--verify`。

---

## 7. 安全要求（重要，必须实现）
1. 任何时候按 F9 立即暂停；F10 立即退出；F7 开关点击功能；F6 循环切换点击模式；F8 重新校准。
2. 鼠标移动、点击、按下、释放都用 try/except 包裹，异常不能导致崩溃。
3. 启动时在终端和调试窗口显示热键说明。
4. 暂停、退出、丢脸、异常时，若正在拖拽必须先释放左键。
5. README 建议首次运行先用 `--camera-test`，再 `--dry-run`，最后才正式模式。
6. 不得上传或保存任何摄像头图像；**只保存校准的数值特征**。README 声明隐私：所有处理均在本地。

---

## 8. 测试要求（pytest，必须全部通过）
所有测试不依赖摄像头和显示器，使用显式传入的时间戳，**不得使用 time.sleep**。涉及 `tools/` 的测试一律使用 `tmp_path` 作为 `root`，**不得写入真实的 `audit_logs/` 和 `docs/`**。

### 8.1 test_filters.py
静止输入输出稳定；阶跃输入最终收敛；`reset()` 有效；dt≤0 返回上次输出。
### 8.2 test_click_detector.py
合成 EAR 序列：基线 0.30，睁眼 0.30，闭眼 0.05，采样 30Hz。
1. 单次 0.15s 眨眼 → 结算后无事件（actions[1]="none"）。
2. 两次 0.15s 眨眼，间隔 0.2s → 结算后恰好 1 个 `left_click`，`blink_count==2`。
3. 三次 → `right_click`；四次 → `double_click`；五次 → `toggle_drag`。
4. 两次眨眼间隔 0.8s（>group_gap）→ 两个独立单次序列，不触发。
5. 其中一次闭眼 0.9s（>blink_max_duration）→ 序列作废，无事件。
6. 闭眼 0.03s 的噪声不计数；且噪声发生在序列开头时，其快照被丢弃，不影响随后真正序列的位置。
7. 7 次眨眼（>max_blinks）→ 无事件。
8. 冷却期内第二组不触发；冷却过后可触发。
9. **位置快照**：构造持续移动的光标历史（例如 x 随时间线性增长），第一次闭眼时取得快照；之后序列持续 3 秒以上（5 次眨眼），期间不再推送位置，结算后事件的 `position` 仍等于"第一次闭眼前 `freeze_lookback`（0.3s）"那一刻的光标位置。
10. **快照边界**：历史不足 0.3 秒时取最早一条；历史为空时使用当前 `gaze_xy`。
11. 序列中 `face_ok=False` 清空序列和快照；随后新序列重新取快照。
12. 迟滞：EAR 在 close/open 阈值之间抖动不产生额外计数。
13. 修改 config 的 actions 映射后行为随之改变。
14. 停留点击：停留 1.3 秒触发一次；不移动不重复触发；移出后再停留可再次触发；`face_ok=False` 重置。
15. `mode=none` 始终无事件；`mode=dwell` 时眨眼不触发。
16. `in_sequence()`、`pending_count()` 在序列进行中返回正确值；`settle_remaining()` 在 0 到 `group_gap` 之间。

### 8.3 test_features.py
构造假 `FaceLandmarks`（人为设定眼角、虹膜位置），验证 x_ratio/y_ratio 与 EAR 数值；含 NaN 时 `build_feature_vector` 返回 None。

### 8.4 test_calibration.py
用合成数据（已知线性映射 + 噪声）训练，验证预测误差小于阈值；保存/加载往返一致；屏幕尺寸不匹配时给出提示；保存文件是合法 JSON 且不含 pickle；覆盖保存时旧文件被复制为 `.bak.json` 而不是被删除。

### 8.5 test_config.py
缺省值、非法值报错（非法动作名、`close_ratio >= open_ratio`、`blink_min_duration >= blink_max_duration`、actions 键越界、`calibration.file` 指向 `data/` 之外）。

### 8.6 test_tools.py
- `log_change`：序号递增、相对路径转绝对路径、md 与 json 同步、固定小节不被破坏、工作区外路径缺少 `--audit-seq` 时被拒绝。
- `record_env --verify`：文件缺失、未登记新文件、sha256 不一致时退出码为 1；一致时为 0；`audit_logs/` 不被当作未登记文件。

### 8.7 test_audit.py
- `log` 追加后文件行数增加，哈希链连续；
- 手动篡改某行后 `--verify-chain` 返回 1；
- `guard_outside_write` 返回 PLANNED 的 seq，DONE 记录的 `ref_seq` 正确；
- `is_outside_workspace` 能识别 `..` 逃逸和符号链接逃逸；
- `safe_delete` 对工作区外路径抛 `PermissionError` 并写 BLOCKED；对 `audit_logs/` 及其内部文件、工作区根目录同样拒绝；对工作区内普通文件成功删除并登记；
- 模块中不存在删除或清空日志的公开函数（用 `dir()` 断言）。

运行 `pytest -q` 必须全绿。

---

## 9. README.md 内容（中文）
包含：项目简介、安装（Python 版本要求、虚拟环境创建与激活）、快速开始（`--camera-test` → `--dry-run` → 正式）、校准指南（光线、头部位置、距离 50~70cm、摄像头置于屏幕上方中央）、**连续眨眼操作指南**（映射表、节奏建议、延迟原因）、热键表、配置项说明、常见问题（光标漂移、眨眼误识别、点击误触、帧率低、macOS 摄像头与辅助功能权限、Linux Wayland 限制）、已知限制、设计决定、隐私说明，以及：

- **设计决定**中必须包含这几条：
  - 点击位置取序列开头的快照，所以眨眼过程中光标不会漂移；
  - 暂停（F9 或 `toggle_pause` 动作）后检测器停止运行，**只能用 F9 恢复**，不能用眨眼恢复，这是为了安全；
  - 校准先收集初始 EAR 基线，再采样，最后用全程数据重算最终基线。
- **调参指南**：
  - 两次眨眼总被识别成一次或两组 → 调大 `group_gap`（0.6~0.7）；
  - 自然眨眼被误识别 → 调小 `close_ratio`（如 0.5），或把 2 次的动作改为 3 次起步；
  - 眼睛较小或戴眼镜 → 可把 `blink_min_duration` 放宽到 0.04；
  - 眨眼太快识别不到 → 检查帧率，低于 20 FPS 时闭眼帧数不足。
- **「变更与卸载」章节**：说明地址表位置 `docs/CHANGE_MANIFEST.md`；审计日志位置 `audit_logs/` 及"永不删除"的原则；如何用 `record_env.py --verify` 与 `audit_log.py --verify-chain` 自检；如何完整卸载（保留 `audit_logs/`）。

---

## 10. 禁止事项
- 禁止使用 pickle、eval、exec。
- 禁止硬编码屏幕分辨率。
- 禁止在主循环里做阻塞式 `time.sleep` 超过 5ms。
- 禁止使用 mediapipe 的 `tasks` 新 API。
- 禁止省略代码（不要写 "..." 或 "此处省略"），所有文件必须完整可运行。
- 禁止擅自增加依赖库；需要新增必须写进 requirements.txt 并说明原因；`tools/` 只能用标准库。
- 禁止全局 pip install；禁止修改系统环境变量、注册表、PATH。
- 禁止删除工作区之外的任何文件（唯一例外：pip 安装依赖过程中的内部处理）。
- 禁止对工作区之外的文件做未留日志的修改。
- 禁止删除、截断、覆盖、重命名 `audit_logs/` 及其中任何文件。
- 禁止在工作区内绕过 `tools/safe_delete.py` 直接删除文件。
- 禁止在没有运行测试的情况下声称"已完成"。

---

## 11. 工作区外操作决策流程（每次执行命令前套用）
```
要执行的操作 → 是否影响工作区之外？
   否 → 正常执行，并登记地址表
   是 → 是否为删除？
          是 → 禁止（pip 安装内部处理除外）；写 BLOCKED 日志；改用工作区内方案
          否 → 能否改成只在工作区内操作？
                 能 → 改写后执行
                 不能 → guard_outside_write 写 PLANNED → 执行 → 写 DONE/FAILED
                        → log_change.py 登记「工作区外修改」并带上 --audit-seq
```

---
## 12. 开发步骤（严格按序，每步结束都要登记地址表）
0. **引导步骤（顺序固定）**：
   - 0a. 先用系统自带的 Python，只依赖标准库，创建 `tools/audit_log.py`、`tools/log_change.py`、`tools/safe_delete.py`、`docs/CHANGE_MANIFEST.md`、`docs/change_manifest.json` 的初始版本，以及 `audit_logs/` 目录。此时不安装任何东西，也不创建 `.venv`。
   - 0b. 运行 `python tools/log_change.py` 登记上一步创建的所有文件和目录（类型：新建文件 / 创建目录）。如果任务提示词文件 `TASK_PROMPT.md` 放在工作区内，也在这里登记为「新建文件」，回滚方式写"可删除，仅为任务说明"。
   - 0c. 创建 `requirements.txt`；创建 `.venv`（`python -m venv .venv`）；创建 `.tmp/`；登记（创建目录、新建文件）。
   - 0d. 在 `.venv` 内执行 `pip install --no-cache-dir -r requirements.txt`（仅在该命令的子进程环境中把 `TMPDIR`/`TEMP`/`TMP` 指向 `<工作区>/.tmp/`）。执行前先过第 2.2 节 E 项的自检清单；若 pip 不可避免地写了工作区外缓存，必须先写 PLANNED 审计记录，完成后写 DONE/FAILED。
   - 0e. 登记「安装依赖」（每个包一条，或用 `record_env.py` 生成清单后统一登记，但必须在安装完成后立即登记）。
1. 创建目录结构、`config.yaml`、`config.py` 及 `test_config.py`；登记。
2. 实现 `filters.py`、`click_detector.py` 及测试；运行相关测试；登记。
3. 实现 `landmarks.py`、`head_pose.py`、`features.py` 及测试；登记。
4. 实现 `calibration.py`（含初始基线阶段与眨眼练习）及测试；登记。
5. 实现 `camera.py`、`mouse.py`、`hotkeys.py`、`ui.py`；登记。
6. 实现 `app.py`、`main.py`；登记。
7. 实现 `tools/record_env.py`，并编写 `test_tools.py`、`test_audit.py`；登记。
8. 运行 `pytest -q`，修复所有失败。
9. 运行 `python main.py --help` 与 `python -c "import eyemouse"`；无摄像头环境下确认 `--camera-test` 给出友好中文错误而不是堆栈。
10. 运行 `python tools/record_env.py --refresh`、`--verify`、`python tools/audit_log.py --verify-chain`，修正所有偏差。
11. 编写 README；登记；再次运行 `--verify`，退出码必须为 0。
12. 输出「完成报告」（见第 14 节）。

---

## 13. 验收标准
- [ ] `pytest -q` 全部通过
- [ ] `python main.py --camera-test` 能显示关键点（有摄像头时）
- [ ] `python main.py --dry-run` 能完成校准（含眨眼练习）并打印光标坐标日志
- [ ] 正式模式下 F9/F10 即时生效；F6 可循环切换点击模式
- [ ] 快速眨眼 2 次 → 约 0.5s 后左键点击；3 次 → 右键；4 次 → 双击；5 次 → 进入/退出拖拽
- [ ] 单次自然眨眼不触发任何动作
- [ ] 眨眼序列进行中光标不漂移
- [ ] 无人脸时光标不乱跳；拖拽中丢脸或暂停会自动释放左键
- [ ] `docs/CHANGE_MANIFEST.md` 存在，路径均为绝对路径，系统级改动为「无」
- [ ] `audit_logs/` 存在，`python tools/audit_log.py --verify-chain` 退出码为 0
- [ ] 整个开发过程中没有删除任何工作区之外的文件，`audit_logs/` 完整无缺
- [ ] `python tools/record_env.py --verify` 退出码为 0
- [ ] 代码无 TODO 占位、无未使用的导入、结构与第 3 节一致

---

## 14. 完成报告（最后一步输出，必须包含）
1. 文件清单与各文件作用；
2. `pytest -q` 的实际输出；
3. 未实现或有限制的部分；
4. 地址表的绝对路径，及最终内容摘要（环境概览 + 依赖清单 + 工作区外操作汇总 + 系统级改动=无）；
5. 审计日志目录的绝对路径、文件列表、条目总数、`--verify-chain` 的结果；
6. 是否有任何工作区之外的修改（列出每条对应的审计 seq；应为「无」或仅有 pip 缓存相关记录）；
7. 确认没有删除任何工作区之外的文件；
8. `.venv` 的绝对路径与占用磁盘大小估计；
9. 我在真机上的测试步骤：先 `--camera-test`，再 `--dry-run`，再正式运行；
10. 我练习连续眨眼的推荐步骤，以及如何调 `group_gap`、`close_ratio`。
