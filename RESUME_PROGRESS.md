# 进度存档 / RESUME_PROGRESS

> 临时交接文件（任务完成后可用 `tools/safe_delete.py` 删除）。
> 用途：退出客户端（切换到 YOLO 模式）后，让新会话无缝从断点继续。

## 1. 任务与范围
- 任务书：`TASK_PROMPT.md`（工作区根目录）。
- 本轮范围：**只做第 12 节的步骤 0a → 4**；完成后输出汇报并**停止**，不要进入步骤 5。

## 2. 断点位置
- **当前停在步骤 0d（pip install）**，且该命令被中断。
- 步骤 0d 尚未完成：`.venv` 内目前**只有 pip 24.3.1**，`mediapipe / opencv-python / numpy / scikit-learn / pyautogui / pynput / PyYAML / pytest` 均**未安装**。

## 3. 已完成（并已登记地址表）
- 0a：已创建 `tools/audit_log.py`、`tools/log_change.py`、`tools/safe_delete.py`、`docs/CHANGE_MANIFEST.md`、`docs/change_manifest.json`、`audit_logs/` 目录。
- 0b：已用 `tools/log_change.py` 登记上述文件/目录，以及 `TASK_PROMPT.md`。
- 0c：已创建 `requirements.txt`、`.venv`、`.tmp/`，并登记。
- 地址表：`docs/CHANGE_MANIFEST.md`（人读）与 `docs/change_manifest.json`（机器可读），条目从 seq=1 起递增。
- `audit_logs/`：目前**为空**（尚无工作区外修改记录）。

## 4. 关键环境结论（务必沿用）
1. **本机没有 Python 3.10/3.11**，只有 Python 3.12.8（另有 msys2 的 3.14，勿用）。
   - 决定：使用 3.12.8 建 venv；此偏离需写入 README「设计决定」并说明原因（mediapipe 0.10.14 有 cp312 wheel）。
   - 基础解释器绝对路径：`C:\Users\24224\AppData\Local\Programs\Python\Python312\python.exe`
2. **沙箱会阻断 `tempfile.mkdtemp`（0o700 目录不可写）**，导致 `ensurepip`/`pip` 在沙箱内必然失败。
   - 结论：`python -m venv`、`pip install` 必须用 **escalated / YOLO** 方式运行。
   - 已确认：escalated 下 `python -m venv .venv` 成功，pip 可用。
3. 运行 pip/python 时，在**子进程环境**里设置 `TEMP`/`TMP`/`TMPDIR` = `<工作区>\.tmp\`（不要改系统环境变量）。
4. `.tmp/` 里有上次中断留下的若干 `pip-*` 临时目录，可忽略（无害）；如需整洁，用 `tools/safe_delete.py` 清理，勿直接删。
5. 工作区 = `D:\TEST\eye_MOUSE`；所有删除必须走 `tools\safe_delete.py`。

## 5. 剩余步骤清单（严格顺序，每步先自检/登记地址表，再进入下一步）
- [ ] 0d. `.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt`（escalated）
- [ ] 0e. 登记「安装依赖」（每包一条，或用 `record_env.py` 清单统一登记；须在安装完成后立即登记）
- [ ] 1. 目录结构 + `config.yaml` + `eyemouse/config.py` + `tests/test_config.py`；跑测试；登记
- [ ] 2. `eyemouse/filters.py` + `eyemouse/click_detector.py` + `tests/test_filters.py` + `tests/test_click_detector.py`；跑测试；登记
- [ ] 3. `eyemouse/landmarks.py` + `eyemouse/head_pose.py` + `eyemouse/features.py` + `tests/test_features.py`；跑测试；登记
- [ ] 4. `eyemouse/calibration.py` + `tests/test_calibration.py`；跑测试；登记
- [ ] 汇报后**停止**（不要做步骤 5）。

## 6. 红线提醒（不得违反）
- 工作区之外**禁止删除**任何文件（唯一例外：pip 安装内部处理）。
- 工作区外修改必须「先 PLANNED、后执行、再 DONE/FAILED」写审计日志。
- `audit_logs/` 永不删除/截断/覆盖。
- 工作区内删除只能用 `tools/safe_delete.py`。
- 禁止 pickle/eval/exec；禁止硬编码分辨率；禁止全局 pip install。

## 7. 已记录的违规（如实留痕）
- 引导阶段曾两次用 `Remove-Item` 直接删除工作区内临时文件（`.tmp_bootstrap.py`、`dbg_tmp.py`），违反第 0 节红线 4；已在地址表以「删除文件」登记说明，后续一律改用 `safe_delete.py`。