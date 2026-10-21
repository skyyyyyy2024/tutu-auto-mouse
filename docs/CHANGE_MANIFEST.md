# 环境与变更地址表

本文件由 `tools/log_change.py` 追加维护，`tools/record_env.py --refresh` 刷新固定小节。
历史记录只增不减；审计日志见 `audit_logs/`，永不删除。

## 变更记录

| 序号 | 时间(本地) | 类型 | 绝对路径 | 说明/目的 | 回滚方式 |
|---|---|---|---|---|---|
| 1 | 2026-10-02T23:52:58 | 创建目录 | `D:\TEST\eye_MOUSE\tools` | 项目工具目录 | 删除空目录 tools |
| 2 | 2026-10-02T23:52:58 | 创建目录 | `D:\TEST\eye_MOUSE\docs` | 文档目录 | 删除空目录 docs |
| 3 | 2026-10-02T23:52:58 | 创建目录 | `D:\TEST\eye_MOUSE\audit_logs` | 审计日志唯一目录，永不删除 | 禁止删除 |
| 4 | 2026-10-02T23:52:58 | 新建文件 | `D:\TEST\eye_MOUSE\tools\audit_log.py` | 审计日志工具（只追加、哈希链） | 删除该文件 |
| 5 | 2026-10-02T23:52:58 | 新建文件 | `D:\TEST\eye_MOUSE\tools\log_change.py` | 地址表写入工具 | 删除该文件 |
| 6 | 2026-10-02T23:52:59 | 新建文件 | `D:\TEST\eye_MOUSE\tools\safe_delete.py` | 受保护删除工具 | 删除该文件 |
| 7 | 2026-10-02T23:52:59 | 新建文件 | `D:\TEST\eye_MOUSE\docs\CHANGE_MANIFEST.md` | 环境与变更地址表（人读） | 删除该文件 |
| 8 | 2026-10-02T23:52:59 | 新建文件 | `D:\TEST\eye_MOUSE\docs\change_manifest.json` | 地址表机器可读版 | 删除该文件 |
| 9 | 2026-10-02T23:52:59 | 新建文件 | `D:\TEST\eye_MOUSE\TASK_PROMPT.md` | 任务说明文件 | 可删除，仅为任务说明 |
| 10 | 2026-10-02T23:52:59 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp_bootstrap.py` | 引导用临时脚本；本次误用 Remove-Item 直接删除，违反第0节红线4（工作区内删除须走 safe_delete.py），特此登记，后续一律改用 safe_delete.py | 无法恢复（临时脚本，无价值内容） |
| 11 | 2026-10-02T23:54:14 | 新建文件 | `D:\TEST\eye_MOUSE\requirements.txt` | 固定依赖版本清单 | 删除该文件 |
| 12 | 2026-10-02T23:54:14 | 创建目录 | `D:\TEST\eye_MOUSE\.venv` | 项目内虚拟环境（Python 3.12.8；本机无 3.10/3.11） | 删除 .venv 目录（用 safe_delete.py） |
| 13 | 2026-10-02T23:54:15 | 创建目录 | `D:\TEST\eye_MOUSE\.tmp` | pip 等临时目录（工作区内） | 删除 .tmp 目录（用 safe_delete.py） |
| 14 | 2026-10-02T23:54:23 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\sub1` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 15 | 2026-10-02T23:54:23 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\tmp1_5gg5_2` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 16 | 2026-10-02T23:54:23 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\tmp4bya1d1m` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 17 | 2026-10-02T23:54:23 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\tmp8sdu_3h2` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 18 | 2026-10-02T23:54:23 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\direct.txt` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 19 | 2026-10-02T23:54:24 | 删除文件 | `D:\TEST\eye_MOUSE\dbg_tmp2.py` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 20 | 2026-10-02T23:54:24 | 删除文件 | `D:\TEST\eye_MOUSE\subroot` | 清理第0a/0c步调试残留（工作区内） | 无法恢复（已删除） |
| 21 | 2026-10-02T23:54:24 | 删除文件 | `D:\TEST\eye_MOUSE\dbg_tmp.py` | 调试脚本；误用 Remove-Item 直接删除，违反第0节红线4，特此登记 | 无法恢复（无价值临时脚本） |
| 22 | 2026-10-02T23:57:29 | 新建文件 | `D:\TEST\eye_MOUSE\RESUME_PROGRESS.md` | 断点续跑用的临时交接文件（YOLO 模式切换） | 任务完成后用 tools\safe_delete.py 删除该文件 |
| 23 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\mediapipe-0.10.14.dist-info` | pip 安装依赖 mediapipe==0.10.14（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall mediapipe（保留 audit_logs/） |
| 24 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\opencv_python-4.9.0.80.dist-info` | pip 安装依赖 opencv-python==4.9.0.80（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall opencv-python（保留 audit_logs/） |
| 25 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\numpy-1.26.4.dist-info` | pip 安装依赖 numpy==1.26.4（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall numpy（保留 audit_logs/） |
| 26 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\scikit_learn-1.9.1.dist-info` | pip 安装依赖 scikit-learn==1.9.1（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall scikit-learn（保留 audit_logs/） |
| 27 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\pyautogui-0.9.54.dist-info` | pip 安装依赖 pyautogui==0.9.54（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall pyautogui（保留 audit_logs/） |
| 28 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\pynput-1.8.2.dist-info` | pip 安装依赖 pynput==1.8.2（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall pynput（保留 audit_logs/） |
| 29 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\pyyaml-6.0.3.dist-info` | pip 安装依赖 PyYAML==6.0.3（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall PyYAML（保留 audit_logs/） |
| 30 | 2026-10-03T00:04:29 | 安装依赖 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages\pytest-9.1.1.dist-info` | pip 安装依赖 pytest==9.1.1（.venv 内，--no-cache-dir） | 在 .venv 内执行 pip uninstall pytest（保留 audit_logs/） |
| 31 | 2026-10-03T00:05:50 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\escape_probe.txt` | 清理 apply_patch 编码探测临时文件（工作区内） | 无法恢复（已删除） |
| 32 | 2026-10-03T00:06:31 | 创建目录 | `D:\TEST\eye_MOUSE\eyemouse` | 项目 Python 包目录 | 删除空目录 eyemouse |
| 33 | 2026-10-03T00:06:31 | 创建目录 | `D:\TEST\eye_MOUSE\tests` | pytest 测试目录 | 删除空目录 tests |
| 34 | 2026-10-03T00:06:31 | 创建目录 | `D:\TEST\eye_MOUSE\data` | 运行时可写入目录（校准/日志） | 删除空目录 data |
| 35 | 2026-10-03T00:06:31 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\__init__.py` | eyemouse 包初始化 | 删除该文件 |
| 36 | 2026-10-03T00:06:31 | 新建文件 | `D:\TEST\eye_MOUSE\config.yaml` | 默认配置文件（写全默认值） | 删除该文件 |
| 37 | 2026-10-03T00:06:31 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | 配置读取/校验（dataclass + 中文报错） | 删除该文件 |
| 38 | 2026-10-03T00:06:31 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_config.py` | 配置模块测试（14 例） | 删除该文件 |
| 39 | 2026-10-03T00:08:13 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\filters.py` | One Euro Filter（1D/2D） | 删除该文件 |
| 40 | 2026-10-03T00:08:13 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\click_detector.py` | 连续眨眼计数状态机 + 注视停留 | 删除该文件 |
| 41 | 2026-10-03T00:08:13 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_filters.py` | 滤波器测试（8 例） | 删除该文件 |
| 42 | 2026-10-03T00:08:13 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_click_detector.py` | 眨眼/停留检测测试（23 例） | 删除该文件 |
| 43 | 2026-10-03T00:09:17 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\landmarks.py` | MediaPipe FaceMesh 封装 + 关键点索引常量 | 删除该文件 |
| 44 | 2026-10-03T00:09:17 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\head_pose.py` | solvePnP 头部姿态估计 | 删除该文件 |
| 45 | 2026-10-03T00:09:17 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\features.py` | EAR/虹膜比例/11 维特征向量 | 删除该文件 |
| 46 | 2026-10-03T00:09:17 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_features.py` | 特征提取测试（6 例） | 删除该文件 |
| 47 | 2026-10-03T00:10:26 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\calibration.py` | 9 点校准 + Ridge 回归 + JSON 保存/加载 + 眨眼练习 | 删除该文件 |
| 48 | 2026-10-03T00:10:26 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_calibration.py` | 校准模型测试（10 例） | 删除该文件 |
| 49 | 2026-10-03T00:12:32 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-3msaa_px` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 50 | 2026-10-03T00:12:32 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-7klesvjs` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 51 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-dt31e4ol` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 52 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-okchbhw_` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 53 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-pvthxgy5` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 54 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-env-qxsfu1wi` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 55 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-build-tracker-o_45tpj1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 56 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-ephem-wheel-cache-engqr88v` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 57 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-install-5ixvhvjp` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 58 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-01ezdy0n` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 59 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-0agleogu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 60 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-0e5cp5cy` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 61 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-0o6vc681` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 62 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-1xmmeat2` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 63 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-217si0kk` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 64 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-27yw4t8n` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 65 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-2e7qjbqd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 66 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-2wxriveu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 67 | 2026-10-03T00:12:33 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-2yyt3xny` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 68 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-3j5bs_wa` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 69 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-3w_x77bb` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 70 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-3wxac9iu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 71 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-3xyd28e0` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 72 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-41v2vc3j` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 73 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-48x0bqwj` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 74 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-4b934zlj` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 75 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-570bgwzj` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 76 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-5c8b7_dl` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 77 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-6ya5cd_d` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 78 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-74_l9ezr` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 79 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-8s9zmawa` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 80 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-9n8ar1p0` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 81 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-9rlw5lr1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 82 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-_82dsxrz` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 83 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-_pevc3kk` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 84 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ak_l7f_6` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 85 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-avvanlcf` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 86 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-b0w8j0m6` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 87 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-b2cjjen7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 88 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-b881f_g3` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 89 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-bkpirh_m` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 90 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-cia9ip2u` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 91 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-cnimiolu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 92 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-d99gru6p` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 93 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-d9uzmjp1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 94 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-dp6cjnyd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 95 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ejymi9e9` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 96 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-eua57mq5` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 97 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ew_c1o5t` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 98 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-fgjiaysh` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 99 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-fljzlg2p` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 100 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-fv9rn6ud` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 101 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ha5slmhq` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 102 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-k3mzusnc` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 103 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-k5uvhrdd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 104 | 2026-10-03T00:12:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-kcn78sqz` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 105 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-kmk6b3u_` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 106 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-l6aqkh40` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 107 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-lqclw17o` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 108 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-luexhi90` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 109 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-lyv38iag` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 110 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-n863mz_t` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 111 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-nnmhmtet` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 112 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-npqi2j18` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 113 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-nsmll_ri` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 114 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-p0j6chip` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 115 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-pjiibi00` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 116 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-r61r4u3s` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 117 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-rnzget4q` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 118 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-s73yj5dp` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 119 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-sp60bheu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 120 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-t29qti4q` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 121 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-t8nnag8b` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 122 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-tgx1izw5` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 123 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-tz9wmkd9` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 124 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ub6fe1bs` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 125 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ug0h7q90` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 126 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ulke3t57` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 127 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-uquf0fma` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 128 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-urmo15uj` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 129 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ut_2dvpe` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 130 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-wf0agat9` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 131 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ww6yqilz` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 132 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-wxba46ce` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 133 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-xgdlbqwx` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 134 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-ymnve8ns` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 135 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-zjb3y13_` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 136 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-metadata-zk9aje2j` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 137 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-3x9kptf7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 138 | 2026-10-03T00:12:35 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-avsunrxu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 139 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-sxeijqqu` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 140 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-ucdsh90_` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 141 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-xy8lfesd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 142 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-modern-metadata-xz1asd5x` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 143 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-0ia3ap_v` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 144 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-0wp7o615` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 145 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-1y60vzed` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 146 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-1ydp6ugv` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 147 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-1z69h7oh` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 148 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-1zywj0y7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 149 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-2ya5ucpf` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 150 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-36173_jr` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 151 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-3_tx7dmi` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 152 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-3h6x445c` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 153 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-3upaiflo` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 154 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-42kmegut` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 155 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-4pqux6ny` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 156 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-4u_h4j2b` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 157 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-5ouixgp5` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 158 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-5tfjm1y8` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 159 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-6dcrgj47` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 160 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-6k2z3qs7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 161 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-6qeqapft` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 162 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-7mu4no81` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 163 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-841gzkcn` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 164 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-8xeib91o` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 165 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-9wntac9r` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 166 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-_8emn0w8` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 167 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-_lu5j1d8` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 168 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-_rcnkmoq` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 169 | 2026-10-03T00:12:36 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-_ue3le6s` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 170 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-aaxbhiom` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 171 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-bdo5mkgh` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 172 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-blb8ue92` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 173 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-bsgejb51` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 174 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-c75cnmcn` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 175 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-ccc0p6kk` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 176 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-d387l2ge` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 177 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-dk629ypm` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 178 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-dn9apix1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 179 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-dujea21n` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 180 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-dx305eip` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 181 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-er2zsqt8` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 182 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-f1vukk9o` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 183 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-f7o_l7x7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 184 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-ffth2bdd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 185 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-fxqc45zp` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 186 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-g4gxytt2` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 187 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-g81muns6` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 188 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-g__5njq1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 189 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-gmwzn5dc` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 190 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-idyc4rgz` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 191 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-iqt961h7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 192 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-lnyfl75n` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 193 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-m8gdcrmi` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 194 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-mdxdg3sh` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 195 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-mojxvsts` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 196 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-mqu7vehq` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 197 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-mvm78n4t` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 198 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-n2ckbgfz` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 199 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-nbpjzaa4` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 200 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-nut4x9kt` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 201 | 2026-10-03T00:12:37 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-nuvuvype` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 202 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-o7toy6m7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 203 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-ocd3lm3p` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 204 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-oljlg13k` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 205 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-p_bqx15q` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 206 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-q7pr14hk` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 207 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-qistarum` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 208 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-qk9b95bb` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 209 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-qv46jtgd` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 210 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-rgez9kzj` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 211 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-rplko1ok` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 212 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-s16xexy1` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 213 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-s_j2akz7` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 214 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-sp9z0wwg` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 215 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-t4k_l_ov` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 216 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-thjpe620` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 217 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-tjmjxcdp` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 218 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-tvi5jdid` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 219 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-ube5pfyt` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 220 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-vd_jjznc` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 221 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-vqcav91h` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 222 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-w41t74qq` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 223 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-x0xvc98j` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 224 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-y676ou3r` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 225 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-y_anq2ig` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 226 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-z_3r5fsf` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 227 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-zd0rpaxs` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 228 | 2026-10-03T00:12:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pip-unpack-zqaq4uqt` | 清理上次中断的 pip 临时目录（工作区内） | 无法恢复（已删除） |
| 229 | 2026-10-03T00:12:42 | 删除文件 | `D:\TEST\eye_MOUSE\tmpkf7sqtpq` | 清理引导阶段残留的空临时目录（工作区内） | 无法恢复（已删除） |
| 230 | 2026-10-03T00:13:23 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\camera.py` | 摄像头封装（打开/读帧镜像/释放/中文报错） | 删除该文件 |
| 231 | 2026-10-03T00:13:23 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\mouse.py` | 鼠标控制封装（pyautogui + dry-run） | 删除该文件 |
| 232 | 2026-10-03T00:13:23 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\hotkeys.py` | 全局热键（pynput，F6-F10） | 删除该文件 |
| 233 | 2026-10-03T00:13:24 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | OpenCV 界面（校准/眨眼练习/调试叠加层） | 删除该文件 |
| 234 | 2026-10-03T00:14:17 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | 主循环状态机（跟踪/暂停/热键/动作/拖拽安全） | 删除该文件 |
| 235 | 2026-10-03T00:14:17 | 新建文件 | `D:\TEST\eye_MOUSE\main.py` | 命令行入口（--camera-test/--dry-run 等） | 删除该文件 |
| 236 | 2026-10-03T00:15:30 | 新建文件 | `D:\TEST\eye_MOUSE\tools\record_env.py` | 环境/依赖清单生成与登记自检（仅标准库） | 删除该文件 |
| 237 | 2026-10-03T00:15:30 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_tools.py` | 地址表与 record_env 自检测试（10 例） | 删除该文件 |
| 238 | 2026-10-03T00:15:30 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_audit.py` | 审计日志与 safe_delete 测试（9 例） | 删除该文件 |
| 239 | 2026-10-03T00:15:30 | 修改文件 | `D:\TEST\eye_MOUSE\tools\log_change.py` | 相对路径改为相对 root 解析（修正登记行为） | 还原为 os.path.abspath(str(path)) |
| 240 | 2026-10-03T00:15:43 | 新建文件 | `D:\TEST\eye_MOUSE\.tmp\camera_test_bad.yaml` | 步骤9 验证 --camera-test 中文报错用的临时配置（camera.index=99） | 删除该文件 |
| 241 | 2026-10-03T00:15:56 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\camera_test_bad.yaml` | 步骤9 验证完成后清理临时配置（工作区内） | 无法恢复（已删除） |
| 242 | 2026-10-03T00:16:07 | 修改文件 | `D:\TEST\eye_MOUSE\tools\record_env.py` | verify 跳过「已登记且随后已登记删除」的路径 | 还原为不跳过的旧版本 |
| 243 | 2026-10-03T00:16:23 | 修改文件 | `D:\TEST\eye_MOUSE\tools\record_env.py` | verify 只比较每个路径最新一次登记（避免历史条目误报） | 还原为遍历全部历史条目的旧版本 |
| 244 | 2026-10-03T00:16:54 | 新建文件 | `D:\TEST\eye_MOUSE\README.md` | 项目说明（安装/快速开始/校准/眨眼指南/热键/配置/FAQ/设计决定/隐私/卸载） | 删除该文件 |
| 245 | 2026-10-03T00:16:54 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤10 自检：record_env --refresh/--verify 与 audit_log --verify-chain 均通过（退出码 0） | 无需回滚（只读校验与地址表刷新） |
| 246 | 2026-10-05T15:00:45 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 247 | 2026-10-05T15:00:58 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 临时运行目录 | 无法恢复（已删除） |
| 248 | 2026-10-05T15:00:58 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-tmp` | 清理 pytest 临时运行目录 | 无法恢复（已删除） |
| 249 | 2026-10-05T15:14:12 | 新建文件 | `D:\TEST\eye_MOUSE\.tmp\camera_test_bad.yaml` | 临时坏配置：camera.index=99，用于验证无摄像头时 --camera-test 的中文报错 | 删除该文件 |
| 250 | 2026-10-05T15:14:34 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\camera_test_bad.yaml` | 验证完毕，清理临时坏配置 | 无法恢复（已删除） |
| 251 | 2026-10-05T15:15:01 | 修改文件 | `D:\TEST\eye_MOUSE\docs\CHANGE_MANIFEST.md` | record_env --refresh 刷新固定小节 | 可重新执行 record_env --refresh 生成 |
| 252 | 2026-10-05T15:15:01 | 修改文件 | `D:\TEST\eye_MOUSE\docs\change_manifest.json` | record_env --refresh 刷新固定小节 | 可重新执行 record_env --refresh 生成 |
| 253 | 2026-10-05T15:15:33 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤12验收：pytest -q -> 80 passed | 无（只读测试） |
| 254 | 2026-10-05T15:15:33 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤12验收：main.py --help 与 import eyemouse 正常 | 无（只读） |
| 255 | 2026-10-05T15:15:34 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤12验收：main.py --camera-test 无摄像头(index=99)时输出中文错误并退出码1 | 无（只读） |
| 256 | 2026-10-05T15:15:34 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤12验收：record_env --refresh(47依赖,0工作区外操作) / --verify 退出码0 / audit_log --verify-chain 通过 | 无（只读） |
| 257 | 2026-10-05T15:15:34 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | 步骤12验收：mediapipe 0.10.14 FaceMesh 在 Python 3.12.8 用合成空白图初始化+detect 成功 | 无（只读） |
| 258 | 2026-10-05T15:49:32 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\enc_probe.txt` | 删除编码探测临时文件 | 无法恢复（已删除） |
| 259 | 2026-10-05T15:49:32 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 临时运行目录 | 无法恢复（已删除） |
| 260 | 2026-10-05T15:49:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\features.py` | A: 新增头部尺度特征，特征向量 11->12 维 | 回滚到 11 维特征实现 |
| 261 | 2026-10-05T15:49:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\filters.py` | B: 新增 FeatureSmoother 特征平滑与 GazeStabilityTracker 注视稳定判定 | 删除新增类 |
| 262 | 2026-10-05T15:49:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | A/B: 新增 head_motion_calibration 配置节、tracking 平滑与稳定参数、默认值调整 | 回滚配置字段 |
| 263 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | A/B: 新增头动校准与平滑/死区/稳定参数 | 回滚 config.yaml |
| 264 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\calibration.py` | A: 头动补偿校准阶段、样本类型、头姿范围、CV 选 alpha、分项误差、超范围限幅 | 回滚 calibration.py |
| 265 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | A/B: show_head_motion 头动提示与调试叠加层坐标/抖动/超范围显示 | 回滚 ui.py |
| 266 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | A/B: 接入特征平滑、注视锁定、头姿限幅与调试信息 | 回滚 app.py |
| 267 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_features.py` | 12 维特征与 refine_landmarks 断言 | 回滚测试 |
| 268 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_calibration.py` | 新增头动补偿/分项误差/CV/限幅/采样阶段测试 | 回滚测试 |
| 269 | 2026-10-05T15:49:33 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_config.py` | 新增 head_motion 与 tracking 新参数测试 | 回滚测试 |
| 270 | 2026-10-05T15:49:34 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_smoothing.py` | B: 特征平滑与注视稳定判定测试 | 删除该文件 |
| 271 | 2026-10-05T15:49:34 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | A/B: 校准流程、配置项、调参指南、设计决定更新 | 回滚 README |
| 272 | 2026-10-05T15:50:01 | 修改文件 | `D:\TEST\eye_MOUSE\docs\CHANGE_MANIFEST.md` | record_env --refresh 刷新固定小节 | 可重新 --refresh 生成 |
| 273 | 2026-10-05T15:50:01 | 修改文件 | `D:\TEST\eye_MOUSE\docs\change_manifest.json` | record_env --refresh 刷新固定小节 | 可重新 --refresh 生成 |
| 274 | 2026-10-05T15:50:01 | 运行命令 | `D:\TEST\eye_MOUSE\.venv\Scripts\python.exe` | A/B 改动后 pytest -q -> 103 passed | 无（只读测试） |
| 275 | 2026-10-05T15:51:39 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | A/B: 恢复跟踪时同样重置平滑/稳定状态 | 回滚 app.py |
| 276 | 2026-10-05T15:51:39 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 临时运行目录 | 无法恢复（已删除） |
| 277 | 2026-10-05T15:53:55 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_calibration.py` | 修正头动合成数据为一致生成模型，分项误差断言更严格 | 回滚测试 |
| 278 | 2026-10-05T15:53:55 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 临时运行目录 | 无法恢复（已删除） |
| 279 | 2026-10-05T16:29:12 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 修复调试叠加层关键点映射：x/y 各自按摄像头帧实际(w,h)与画布(w,h)缩放；新增纯函数 map_point_to_canvas；_draw_face_points 改为接收帧宽高；不使用屏幕坐标或头姿补偿 | git checkout -- eyemouse/ui.py |
| 280 | 2026-10-05T16:29:14 | 新建文件 | `D:\TEST\eye_MOUSE\tools\diagnose_overlay_mapping.py` | 最小复现脚本：合成数据验证校准前后同一组归一化关键点映射到像素坐标是否一致 | 删除该文件 |
| 281 | 2026-10-05T16:29:14 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_ui_overlay.py` | 回归测试：叠加层映射 x/y 独立缩放；同一帧校准前后绘制相对位置一致；绘制签名不含屏幕坐标/头姿参数 | 删除该文件 |
| 282 | 2026-10-05T16:29:47 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 283 | 2026-10-05T18:05:18 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 284 | 2026-10-05T18:20:31 | 新建文件 | `D:\TEST\eye_MOUSE\docs\FACE_PROFILE_DESIGN.md` | 个人面部标定与几何视线估计设计说明（模板、PnP 升级、几何视线、特征/版本、流程、UI、配置、测试与限制） | 删除该文件 |
| 285 | 2026-10-05T18:22:50 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\landmarks.py` | 新增 STABLE_POINT_INDEXES 20 个面部稳定点常量 | git checkout -- eyemouse/landmarks.py |
| 286 | 2026-10-05T18:22:50 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\face_profile.py` | 个人面部 3D 模板：采集/中位数/质量指标/保存加载备份 | 删除该文件 |
| 287 | 2026-10-05T18:22:50 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\head_pose.py` | 头姿升级：个人/通用模板、初值复用、角度回绕平滑、焦距覆盖、重投影误差与可信标记 | git checkout -- eyemouse/head_pose.py |
| 288 | 2026-10-05T18:22:50 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\gaze_geometry.py` | 几何视线：眼球中心后移 + 头坐标系视线角度，双眼平均 | 删除该文件 |
| 289 | 2026-10-05T18:22:50 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\features.py` | 特征 12->14 维，加入 gaze_yaw/gaze_pitch，支持注入头姿 | git checkout -- eyemouse/features.py |
| 290 | 2026-10-05T18:22:50 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | 新增 FaceProfileConfig 与 face_profile 配置节校验 | git checkout -- eyemouse/config.py |
| 291 | 2026-10-05T18:22:51 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 新增 face_profile 配置节 | git checkout -- config.yaml |
| 292 | 2026-10-05T18:24:25 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\calibration.py` | MODEL_VERSION=3、ModelVersionMismatchError、面部标定阶段、头姿估计器注入与特征一致采样 | git checkout -- eyemouse/calibration.py |
| 293 | 2026-10-05T18:24:25 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | 载入/保存面部模板、--recalibrate-face、头姿估计器与视线接入、调试叠加层透传 | git checkout -- eyemouse/app.py |
| 294 | 2026-10-05T18:24:25 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 叠加层显示头姿/视线/重投影误差并绘制头部朝向轴线（沿用 map_point_to_canvas） | git checkout -- eyemouse/ui.py |
| 295 | 2026-10-05T18:24:25 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 新增 --recalibrate-face 参数 | git checkout -- main.py |
| 296 | 2026-10-05T21:04:21 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_face_profile.py` | 面部模板/PnP 角度恢复/回绕平滑/旧模型降级/几何视线/14 维特征测试 | 删除该文件 |
| 297 | 2026-10-05T21:04:21 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_features.py` | 特征维度断言 12->14 | git checkout -- tests/test_features.py |
| 298 | 2026-10-05T21:04:21 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_calibration.py` | 模型版本 3、特征维度 14、头动角度 ∓180 约定 | git checkout -- tests/test_calibration.py |
| 299 | 2026-10-05T21:04:51 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 新增个人面部标定/几何视线说明、--recalibrate-face、face_profile 配置与调参指南、z 深度相对估计限制 | git checkout -- README.md |
| 300 | 2026-10-05T21:04:54 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\aptest.patch` | 清理临时调试/pytest 残留 | 无法恢复（已删除） |
| 301 | 2026-10-05T21:04:54 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\aptest3.txt` | 清理临时调试/pytest 残留 | 无法恢复（已删除） |
| 302 | 2026-10-05T21:04:57 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 303 | 2026-10-05T21:05:12 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\head_pose.py` | 头姿结果新增 axis_length（叠加层头部朝向轴线长度，个人模板 0.5 / 通用模板 40） | git checkout -- eyemouse/head_pose.py |
| 304 | 2026-10-05T21:05:13 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\features.py` | 头姿不可信时不旋转视线方向，避免把位姿误差放大到 gaze 特征 | git checkout -- eyemouse/features.py |
| 305 | 2026-10-05T21:05:18 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 306 | 2026-10-05T21:42:31 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\head_control.py` | C/D: 新增面部朝向（头姿）控制光标模块（velocity/absolute 两种模式、死区/速度曲线、方向可翻转、next_source 来源切换） | 删除 eyemouse/head_control.py |
| 307 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | C/D: 新增 HeadControlConfig 与 head_control 配置节、校验收紧；safety 新增 cursor_key | git checkout -- eyemouse/config.py |
| 308 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | C/D: 新增 head_control 配置节与 safety.cursor_key(F5) | git checkout -- config.yaml |
| 309 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hotkeys.py` | C/D: HotkeyRequests 新增 cycle_cursor 并映射 cursor_key | git checkout -- eyemouse/hotkeys.py |
| 310 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | C/D: 光标来源切换(F5)、头控驱动 _drive_head_cursor，眼控 _drive_eye_cursor 原样保留 | git checkout -- eyemouse/app.py |
| 311 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | C/D: draw_debug 增加 cursor_source 显示 | git checkout -- eyemouse/ui.py |
| 312 | 2026-10-05T21:42:32 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | C/D: 热键帮助新增 F5 切换光标来源说明 | git checkout -- main.py |
| 313 | 2026-10-05T21:42:32 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_head_control.py` | C/D: 头控模块测试（速度曲线/方向/死区/裁剪/dt 上限/absolute/reset/来源切换/配置校验）13 条 | 删除 tests/test_head_control.py |
| 314 | 2026-10-05T21:42:33 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | C/D: 功能特性/F5 热键/head_control 配置说明与调参指南（含上下不灵敏可用头控替代） | git checkout -- README.md |
| 315 | 2026-10-05T21:42:38 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 316 | 2026-10-05T21:48:54 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 头控横纵方向实测均反向，head_control.invert_x/invert_y 置为 true | git checkout -- config.yaml |
| 317 | 2026-10-05T21:49:01 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 318 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\head_control.py` | 新增一键基准点 recenter/center（update 自动扣除基准点），absolute 模式加入死区整形，成为跟手直映射 | git checkout -- eyemouse/head_control.py |
| 319 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | SafetyConfig 新增 baseline_key(f4) 并纳入非空校验 | git checkout -- eyemouse/config.py |
| 320 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | safety 新增 baseline_key=f4；head_control.mode 改为 absolute（跟手） | git checkout -- config.yaml |
| 321 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hotkeys.py` | HotkeyRequests 新增 recenter 并映射 baseline_key | git checkout -- eyemouse/hotkeys.py |
| 322 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | F4 接入 _recenter_baseline：头控设零点并重置平滑；眼控重置平滑 | git checkout -- eyemouse/app.py |
| 323 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 热键帮助新增 F4 一键基准点校准 | git checkout -- main.py |
| 324 | 2026-10-05T21:53:23 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_head_control.py` | 新增基准点/absolute 死区/配置默认 6 条测试（13->19） | git checkout -- tests/test_head_control.py |
| 325 | 2026-10-05T21:53:24 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 说明 absolute 跟手模式与 F4 基准点，补充配置项与调参指南 | git checkout -- README.md |
| 326 | 2026-10-05T21:53:26 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 327 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\head_control.py` | 新增对角增益 diagonal_boost 与脸部平移输入 translation_weight/translation_range；update 支持 face_x，平移基准首帧自动建立，recenter 记录脸位基准 | git checkout -- eyemouse/head_control.py |
| 328 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | HeadControlConfig 新增 diagonal_boost/translation_weight/translation_range 及校验 | git checkout -- eyemouse/config.py |
| 329 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | head_control 新增对角增益与脸部平移参数（0.5/0.5/0.25） | git checkout -- config.yaml |
| 330 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | 新增 face_center_x 计算并传入头控 update/recenter，调试透出 face_x | git checkout -- eyemouse/app.py |
| 331 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 叠加层新增 FaceX 脸部水平中心显示 | git checkout -- eyemouse/ui.py |
| 332 | 2026-10-05T22:22:23 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_head_control.py` | 新增对角增益（含 75% 自然对角反推）、平移输入、自动基准与新配置校验 8 条测试（19->27） | git checkout -- tests/test_head_control.py |
| 333 | 2026-10-05T22:22:24 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 说明对角增益与脸部平移参数、FaceX 显示及调参指南 | git checkout -- README.md |
| 334 | 2026-10-05T22:22:26 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 335 | 2026-10-06T14:59:08 | 新建文件 | `D:\TEST\eye_MOUSE\docs\HAND_CONTROL_DESIGN.md` | 右手控制光标功能设计说明（模块划分/数据流/配置/测试/限制） | 删除 docs/HAND_CONTROL_DESIGN.md |
| 336 | 2026-10-06T14:59:15 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_gesture.py` | 张开手掌判定 is_open_palm 与滞回状态机 OpenPalmGate（纯函数，含手部关键点索引与骨架连接常量） | 删除 eyemouse/hand_gesture.py |
| 337 | 2026-10-06T14:59:25 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_pointer.py` | 手掌中心追踪点与 relative/absolute 光标映射，独立 One Euro 与死区，gate 进入锁定参考防跳变 | 删除 eyemouse/hand_pointer.py |
| 338 | 2026-10-06T14:59:30 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_tracker.py` | MediaPipe Hands 封装：max_num_hands=2/model_complexity=0，mirror_handedness 校正，只返回目标手（默认右手） | 删除 eyemouse/hand_tracker.py |
| 339 | 2026-10-06T15:00:14 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_gesture.py` | 补齐 MIDDLE_MCP/RING_MCP 及各指 DIP 索引常量（修复 hand_pointer 导入失败） | git checkout -- eyemouse/hand_gesture.py |
| 340 | 2026-10-06T15:00:14 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | 新增 HandControlConfig（pointer_source/mirror_handedness/open_ratio/... 共 16 项）与范围校验、AppConfig 字段、config_from_dict 节 | git checkout -- eyemouse/config.py |
| 341 | 2026-10-06T15:00:20 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 新增 hand_control 配置节（手控开关/来源/镜像/手势阈值/映射/滤波/死区/降频/挂起眨眼） | git checkout -- config.yaml |
| 342 | 2026-10-06T15:02:57 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\pytest-of-24224` | 清理 pytest 残留临时目录 | 无法恢复（已删除） |
| 343 | 2026-10-06T15:05:32 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 调试叠加层新增 hand/hand_gate/pointer_source/hand_fps；_draw_hand_points 用 map_point_to_canvas 画手部骨架 | git checkout -- eyemouse/ui.py |
| 344 | 2026-10-06T15:05:33 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | 集成手控：resolve_cursor_driver/should_suspend_blink、_process_hands/_drive_hand_cursor、pointer_source 路由、F9/F10 与暂停重置 | git checkout -- eyemouse/app.py |
| 345 | 2026-10-06T15:05:33 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 新增 --pointer-source 与 --hand-test（只显示手部关键点与 gate 状态，不动鼠标） | git checkout -- main.py |
| 346 | 2026-10-06T15:05:33 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_hand_control.py` | 手控合成测试：张开/握拳/旋转不变、gate 滞回与超时、relative/absolute 映射、driver 选择、配置校验 | 删除 tests/test_hand_control.py |
| 347 | 2026-10-06T15:06:12 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 新增手控说明：功能特性、--hand-test/--pointer-source、hand_control 配置项、调参指南、已知限制、设计决定 12 | git checkout -- README.md |
| 348 | 2026-10-06T15:10:06 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 手控 mirror_handedness 默认改为 false；camera.mirror=true 时 MediaPipe 已给出正确左右手标签，避免二次互换判反 | git checkout -- config.yaml |
| 349 | 2026-10-06T15:10:06 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | HandControlConfig.mirror_handedness 默认 True->False | git checkout -- eyemouse/config.py |
| 350 | 2026-10-06T15:10:06 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_tracker.py` | HandTracker.mirror_handedness 默认 True->False，_correct 注释说明仅在非镜像输入时才互换 | git checkout -- eyemouse/hand_tracker.py |
| 351 | 2026-10-06T15:10:06 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_hand_control.py` | 默认值改 False；新增左右手标签回归测试（镜像不互换/非镜像互换/默认配置不自相矛盾） | git checkout -- tests/test_hand_control.py |
| 352 | 2026-10-06T15:10:07 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 更新 mirror_handedness 默认值与调参/已知限制说明（与 camera.mirror 配套） | git checkout -- README.md |
| 353 | 2026-10-06T15:10:07 | 修改文件 | `D:\TEST\eye_MOUSE\docs\HAND_CONTROL_DESIGN.md` | 同步 mirror_handedness 设计说明与默认值 false | git checkout -- docs/HAND_CONTROL_DESIGN.md |
| 354 | 2026-10-06T15:13:30 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 修复致命崩溃：_draw_head_axis 丢失 @staticmethod（手部绘制方法插入时误留重复装饰器），经实例调用多传 self 导致 TypeError，程序启动即退出 | git checkout -- eyemouse/ui.py |
| 355 | 2026-10-06T15:13:30 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_ui_overlay.py` | 新增回归：_draw_head_axis 必须为 staticmethod，且经实例调用与 draw_debug 同路径不得抛 TypeError | git checkout -- tests/test_ui_overlay.py |
| 356 | 2026-10-06T15:15:08 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 手控灵敏度 gain 1.2 -> 2.4（提高两倍） | git checkout -- config.yaml |
| 357 | 2026-10-06T15:15:08 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | HandControlConfig.gain 默认 1.2 -> 2.4 | git checkout -- eyemouse/config.py |
| 358 | 2026-10-06T15:15:08 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_hand_control.py` | 默认 gain 断言同步为 2.4 | git checkout -- tests/test_hand_control.py |
| 359 | 2026-10-06T15:15:08 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 调参指南默认 gain 更新为 2.4 | git checkout -- README.md |
| 360 | 2026-10-06T15:15:08 | 修改文件 | `D:\TEST\eye_MOUSE\docs\HAND_CONTROL_DESIGN.md` | 设计表 gain 默认值更新为 2.4 | git checkout -- docs/HAND_CONTROL_DESIGN.md |
| 361 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_pointer.py` | 新增 tracking_point(points, mode)：palm/wrist/index_tip/thumb_tip 追踪点可选，palm_center 改为其 palm 别名 | git checkout -- eyemouse/hand_pointer.py |
| 362 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\hand_gesture.py` | is_open_palm 新增 require_thumb 参数（默认 true），可关闭拇指条件 | git checkout -- eyemouse/hand_gesture.py |
| 363 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | HandControlConfig 新增 tracking_point 与 require_thumb 及取值校验 | git checkout -- eyemouse/config.py |
| 364 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | hand_control 新增 tracking_point=palm 与 require_thumb=true | git checkout -- config.yaml |
| 365 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\app.py` | 手控改用可配置追踪点；gate 传入 require_thumb；新增 hand_point 状态与调试字段 | git checkout -- eyemouse/app.py |
| 366 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 叠加层用洋红圆圈标出实际追踪点（hand_point） | git checkout -- eyemouse/ui.py |
| 367 | 2026-10-06T15:25:02 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_hand_control.py` | 新增追踪点模式、模式切换、require_thumb 开关测试；默认值与非法 tracking_point 校验 | git checkout -- tests/test_hand_control.py |
| 368 | 2026-10-06T15:25:03 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 记录 tracking_point/require_thumb 配置与『光标像跟着大拇指』排查步骤 | git checkout -- README.md |
| 369 | 2026-10-06T15:25:03 | 修改文件 | `D:\TEST\eye_MOUSE\docs\HAND_CONTROL_DESIGN.md` | 设计表补充 tracking_point 与 require_thumb | git checkout -- docs/HAND_CONTROL_DESIGN.md |
| 370 | 2026-10-06T15:25:41 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 手控控制点默认改为大拇指指尖 tracking_point=thumb_tip | git checkout -- config.yaml |
| 371 | 2026-10-06T15:25:41 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | HandControlConfig.tracking_point 默认 palm -> thumb_tip | git checkout -- eyemouse/config.py |
| 372 | 2026-10-06T15:25:41 | 修改文件 | `D:\TEST\eye_MOUSE\tests\test_hand_control.py` | 默认 tracking_point 断言同步为 thumb_tip | git checkout -- tests/test_hand_control.py |
| 373 | 2026-10-06T15:25:41 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 说明默认控制点为大拇指指尖，并更新调参条目 | git checkout -- README.md |
| 374 | 2026-10-06T15:25:41 | 修改文件 | `D:\TEST\eye_MOUSE\docs\HAND_CONTROL_DESIGN.md` | tracking_point 默认值更新为 thumb_tip | git checkout -- docs/HAND_CONTROL_DESIGN.md |
| 375 | 2026-10-06T15:30:32 | 新建文件 | `D:\TEST\eye_MOUSE\docs\EYEMOUSE_REPORT.md` | 面向开发者的项目状态报告：功能、环境偏离、配置项、模块结构、测试、工程机制、已知坑与待办 | 删除 docs/EYEMOUSE_REPORT.md |
| 376 | 2026-10-10T15:44:07 | 新建文件 | `D:\TEST\eye_MOUSE\docs\GLASSES_TRACKING_DESIGN.md` | 眼镜刚体六自由度追踪设计说明：坐标系/单位/镜像规则、阶段一内参与标记追踪与失效策略、阶段二三设计、硬件与测试要求 | 删除 docs/GLASSES_TRACKING_DESIGN.md |
| 377 | 2026-10-10T16:00:01 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\config.py` | 新增 camera_calibration/glasses_tracking 两节配置与严格校验，AppConfig 增加字段，数据路径校验覆盖内参文件（眼镜追踪阶段一） | git checkout -- eyemouse/config.py |
| 378 | 2026-10-10T16:00:08 | 修改文件 | `D:\TEST\eye_MOUSE\config.yaml` | 新增 camera_calibration 与 glasses_tracking 两节（含中文注释），默认值与应用配置一致；眼镜追踪默认关闭，不改变现有行为 | git checkout -- config.yaml |
| 379 | 2026-10-10T16:00:08 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\camera.py` | 新增向后兼容 read_raw()：返回未镜像原始帧；read() 改为 read_raw()+按配置镜像，几何处理可用未镜像画面 | git checkout -- eyemouse/camera.py |
| 380 | 2026-10-10T16:00:08 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\camera_calibration.py` | 摄像头内参标定：ChArUco 板检测/标定/质量检查/JSON 存读与备份；标定板按物理尺寸精确渲染并自检方格像素尺寸 | 删除 eyemouse/camera_calibration.py |
| 381 | 2026-10-10T16:00:08 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\glasses_tracker.py` | 眼镜 ArUco 标记六自由度追踪：IPPE_SQUARE 候选、正深度/旋转/重投影质量门、多帧证据与连续性解歧义、四元数 SLERP 平滑、独立平移滤波与失效状态机 | 删除 eyemouse/glasses_tracker.py |
| 382 | 2026-10-10T16:00:08 | 修改文件 | `D:\TEST\eye_MOUSE\eyemouse\ui.py` | 新增 flip_display_point() 与 draw_glasses_overlay()：把未镜像几何结果换算到镜像显示并绘制标记边界/ID/三色坐标轴/状态与统计 | git checkout -- eyemouse/ui.py |
| 383 | 2026-10-10T16:00:08 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 新增 --calibrate-camera / --glasses-test / --write-charuco-board 三个模式：均不实例化鼠标控制、不触发点击；默认 pointer_source 不变 | git checkout -- main.py |
| 384 | 2026-10-10T16:00:14 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_camera_calibration.py` | 摄像头标定测试：板参数/字典/渲染物理比例/角点顺序/合成标定恢复内参/存读版本备份/非法值，全部合成数据 | 删除 tests/test_camera_calibration.py |
| 385 | 2026-10-10T16:00:14 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_glasses_tracking.py` | 眼镜追踪测试：四元数与角度回绕/SLERP、IPPE 候选质量门与歧义（连续性+多帧证据）、缺失/过小/NaN/运动离群/分辨率不符、镜像只影响显示、CLI 不创建鼠标、配置校验 | 删除 tests/test_glasses_tracking.py |
| 386 | 2026-10-10T16:00:14 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 新增眼镜标记六自由度追踪（阶段一）章节：硬件、标定板打印与实测核验、内参标定、--glasses-test 用法、歧义与精度说明；补充配置项、已知限制与设计决定 | git checkout -- README.md |
| 387 | 2026-10-10T16:00:14 | 修改文件 | `D:\TEST\eye_MOUSE\docs\GLASSES_TRACKING_DESIGN.md` | 按实现实测结果补充：平面标记双解统计与证据累积策略、显示用欧拉角 0 基准、标定板渲染缩放的坑、stabilize_frames 死锁回归 | git checkout -- docs/GLASSES_TRACKING_DESIGN.md |
| 388 | 2026-10-10T16:00:15 | 新建文件 | `D:\TEST\eye_MOUSE\data\charuco_board.png` | 生成的 8x6 ChArUco 可打印标定板（4000px/m 精确渲染，4000px/m=101.6dpi 元数据），供用户 100% 实际尺寸打印；可用 main.py --write-charuco-board 重新生成 | 删除 data/charuco_board.png |
| 389 | 2026-10-10T16:00:27 | 新建文件 | `D:\TEST\eye_MOUSE\docs\EyeMouse 眼镜六自由度追踪开发提示词.md` | 用户放置的任务提示词（眼镜刚体六自由度追踪），登记以保持地址表自检一致 | 删除 docs/EyeMouse 眼镜六自由度追踪开发提示词.md |
| 390 | 2026-10-10T16:01:17 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 补 typing 导入 Any（新增模式函数的类型注解），无行为变化 | git checkout -- main.py |
| 391 | 2026-10-10T16:01:39 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 补充阶段一数据文件格式字段表与真机验证记录表（12 项） | git checkout -- README.md |
| 392 | 2026-10-10T16:24:11 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\probe_apply.py` | 本轮临时探针/试渲染产物（.tmp 内），用毕清理 | 无法恢复（已删除） |
| 393 | 2026-10-10T16:24:11 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\probe_dq.py` | 本轮临时探针/试渲染产物（.tmp 内），用毕清理 | 无法恢复（已删除） |
| 394 | 2026-10-10T16:24:11 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\marker_smoke.png` | 本轮临时探针/试渲染产物（.tmp 内），用毕清理 | 无法恢复（已删除） |
| 395 | 2026-10-10T16:24:12 | 删除文件 | `D:\TEST\eye_MOUSE\.tmp\marker_cli.png` | 本轮临时探针/试渲染产物（.tmp 内），用毕清理 | 无法恢复（已删除） |
| 396 | 2026-10-10T16:25:27 | 新建文件 | `D:\TEST\eye_MOUSE\eyemouse\marker_sheet.py` | 打印用眼镜 ArUco 单标记图纸：按 glasses_tracking 的字典/id/黑框边长精确渲染（先吸附整数格，再用整数 px/m 写 PNG pHYs），图上自带 0-100mm 毫米参考条与打印/量尺说明，导出前自检黑框像素边长、居中与可检出性；只写 PNG，不开摄像头、不控制鼠标、不改追踪逻辑 | 删除 eyemouse/marker_sheet.py |
| 397 | 2026-10-10T16:25:27 | 修改文件 | `D:\TEST\eye_MOUSE\main.py` | 新增 --write-aruco-marker [PATH] 与 write_aruco_marker()：只导出眼镜单标记打印图纸并打印尺寸与量尺步骤，不打开摄像头、不控制鼠标、不改追踪逻辑 | git checkout -- main.py |
| 398 | 2026-10-10T16:25:27 | 新建文件 | `D:\TEST\eye_MOUSE\tests\test_marker_sheet.py` | 标记图纸测试（26 项，全部合成数据）：整数格吸附与物理尺寸精确、白边留白、渲染自检、可检出 id、参考条长度、pHYs 元数据可还原 30.00mm、配置读取、以及 PnP 距离与图纸尺寸的跨模块契约 | 删除 tests/test_marker_sheet.py |
| 399 | 2026-10-10T16:25:35 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 新增「打印眼镜 ArUco 单标记」小节（命令、100% 实际尺寸、白边要求、量尺 3 步）与 CLI 参数表一行；补充已知限制两条、设计决定 16（图纸尺寸唯一来源是配置/矩形画刻度）、真机验证表第 2 项与隐私说明 | git checkout -- README.md |
| 400 | 2026-10-10T16:25:35 | 修改文件 | `D:\TEST\eye_MOUSE\docs\GLASSES_TRACKING_DESIGN.md` | 新增 5.1.1 可打印单标记图纸：黑框语义（marker_size_m 为黑框外缘边长）、整数格像素吸附与 pHYs、导出前自检、实测兜底、矩形画刻度避免 100mm 参考条变长；硬件清单补「标记图纸」行 | git checkout -- docs/GLASSES_TRACKING_DESIGN.md |
| 401 | 2026-10-10T16:25:35 | 新建文件 | `D:\TEST\eye_MOUSE\data\aruco_marker_id0_30mm.png` | 生成的眼镜单标记打印图纸：DICT_5X5_50 id=0，黑框 357px=30.00mm，每侧白边 10.0mm，整张纸 1464x1785px=123.0x150.0mm，pHYs=11900px/m(302.26dpi)，含 0-100mm 毫米刻度参考条；打印后须真尺实测并回填 glasses_tracking.marker_size_m | 删除 data/aruco_marker_id0_30mm.png |
| 402 | 2026-10-10T16:28:06 | 修改文件 | `D:\TEST\eye_MOUSE\README.md` | 已知限制补一条：单标记固有尺度偏差（亚像素角点约少 1 像素，60px 标记在 0.5m 处约 -1.4%，合成回放实测） | git checkout -- README.md |
| 403 | 2026-10-10T16:28:06 | 修改文件 | `D:\TEST\eye_MOUSE\docs\GLASSES_TRACKING_DESIGN.md` | 已知限制补一条：单标记固有尺度偏差（约 1 像素 / marker_px，合成回放 60px@0.5m 约 -1.4%），阶段二求交需留裕量 | git checkout -- docs/GLASSES_TRACKING_DESIGN.md |
| 404 | 2026-10-21T14:56:59 | 新建文件 | `D:\TEST\eye_MOUSE\.gitignore` | 新增 .gitignore：排除 .venv/缓存/.tmp/.pytmp/audit_logs/ 与 data 下的个人校准 JSON 和运行日志；保留 data 下两张可打印 PNG 图纸 | 删除 .gitignore |
| 405 | 2026-10-21T14:57:21 | 新建文件 | `D:\TEST\eye_MOUSE\.gitattributes` | 新增 .gitattributes：强制 LF 换行（地址表 sha256 需要工作区字节一致），PNG 标记为二进制 | 删除 .gitattributes |

## 环境概览
- 操作系统：Windows 11 (10.0.26200)
- Python 解释器：`D:\TEST\eye_MOUSE\.venv\Scripts\python.exe`
- Python 版本：3.12.8
- 虚拟环境：`D:\TEST\eye_MOUSE\.venv`（在虚拟环境内：是；是项目 .venv：是）
- 项目根目录（工作区）：`D:\TEST\eye_MOUSE`
- 审计日志目录：`D:\TEST\eye_MOUSE\audit_logs`

## 依赖清单

| 名称 | 版本 | 安装位置 | 用途 | 是否在 requirements.txt |
|---|---|---|---|---|
| absl-py | 2.5.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | absl 工具（mediapipe 依赖） | 否 |
| attrs | 26.1.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| cffi | 2.1.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| cloudpickle | 3.1.2 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| colorama | 0.4.6 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 终端颜色（pytest 依赖） | 否 |
| contourpy | 1.3.3 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| cycler | 0.12.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| flatbuffers | 25.12.19 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 序列化（mediapipe 依赖） | 否 |
| fonttools | 4.66.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| iniconfig | 2.3.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| jax | 0.7.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 数值计算（mediapipe 依赖） | 否 |
| jaxlib | 0.7.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | jax 运行时（mediapipe 依赖） | 否 |
| joblib | 1.6.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 并行计算（scikit-learn 依赖） | 否 |
| kiwisolver | 1.5.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| matplotlib | 3.11.2 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 绘图（mediapipe 依赖） | 否 |
| mediapipe | 0.10.14 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 人脸/虹膜关键点检测 | 是 |
| ml_dtypes | 0.5.4 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| MouseInfo | 0.1.3 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| narwhals | 2.26.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| numpy | 1.26.4 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 数值计算 | 是 |
| opencv-contrib-python | 4.11.0.86 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | OpenCV 扩展模块（mediapipe 依赖） | 否 |
| opencv-python | 4.9.0.80 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 图像处理与界面 | 是 |
| opt_einsum | 3.4.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| packaging | 26.3 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pillow | 12.3.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 图像库（matplotlib 依赖） | 否 |
| pip | 24.3.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pluggy | 1.6.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| protobuf | 4.25.9 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 序列化（mediapipe 依赖） | 否 |
| PyAutoGUI | 0.9.54 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 鼠标控制 | 是 |
| pycparser | 3.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| PyGetWindow | 0.0.9 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| Pygments | 2.21.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| PyMsgBox | 2.0.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pynput | 1.8.2 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 全局热键 | 是 |
| pyparsing | 3.3.3 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pyperclip | 1.11.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| PyRect | 0.2.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| PyScreeze | 1.0.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pytest | 9.1.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 单元测试 | 是 |
| python-dateutil | 2.9.0.post0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| pytweening | 1.2.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| PyYAML | 6.0.3 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 配置文件解析 | 是 |
| scikit-learn | 1.9.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 校准回归模型 | 是 |
| scipy | 1.17.1 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 科学计算（scikit-learn 依赖） | 否 |
| six | 1.17.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 间接依赖 | 否 |
| sounddevice | 0.5.6 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 音频（mediapipe 依赖） | 否 |
| threadpoolctl | 3.7.0 | `D:\TEST\eye_MOUSE\.venv\Lib\site-packages` | 线程控制（scikit-learn 依赖） | 否 |

## 运行时会写入的位置
- `<项目>/data/calibration.json`
- `<项目>/data/calibration.<时间戳>.bak.json`
- `<项目>/data/run.log`

## 工作区外操作汇总
无

## 系统级改动
无

## 一键卸载步骤
卸载前请保留 `audit_logs/`（审计日志永不删除）。以下命令仅写入文档，由用户手动执行。

Windows（PowerShell，在项目根目录执行）：

```powershell
Remove-Item -Recurse -Force .venv
Remove-Item -Recurse -Force .tmp
Remove-Item -Recurse -Force data
Remove-Item -Force main.py, config.yaml, requirements.txt, README.md
Remove-Item -Recurse -Force eyemouse, tests, tools, docs
# 保留 .\audit_logs（审计日志永不删除）
```

macOS / Linux（在项目根目录执行）：

```bash
rm -rf .venv .tmp data main.py config.yaml requirements.txt README.md eyemouse tests tools docs
# 保留 ./audit_logs（审计日志永不删除）
```
