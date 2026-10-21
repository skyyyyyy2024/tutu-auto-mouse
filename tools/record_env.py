"""环境与依赖清单工具：生成/刷新地址表固定小节，并自检工作区文件登记情况。

只使用 Python 标准库；所有函数都支持显式传入 ``root``（工作区根目录），
便于测试使用临时目录，不污染真实工作区。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import audit_log  # noqa: E402
import log_change  # noqa: E402

IGNORED_DIR_NAMES = {".venv", ".tmp", "__pycache__", ".pytest_cache", "data", "audit_logs", ".git"}
SOURCE_SUFFIXES = {".py"}

PURPOSE = {
    "mediapipe": "人脸/虹膜关键点检测",
    "opencv-python": "图像处理与界面",
    "opencv-contrib-python": "OpenCV 扩展模块（mediapipe 依赖）",
    "numpy": "数值计算",
    "scikit-learn": "校准回归模型",
    "pyautogui": "鼠标控制",
    "pynput": "全局热键",
    "pyyaml": "配置文件解析",
    "pytest": "单元测试",
    "scipy": "科学计算（scikit-learn 依赖）",
    "jax": "数值计算（mediapipe 依赖）",
    "jaxlib": "jax 运行时（mediapipe 依赖）",
    "matplotlib": "绘图（mediapipe 依赖）",
    "absl-py": "absl 工具（mediapipe 依赖）",
    "protobuf": "序列化（mediapipe 依赖）",
    "flatbuffers": "序列化（mediapipe 依赖）",
    "sounddevice": "音频（mediapipe 依赖）",
    "pillow": "图像库（matplotlib 依赖）",
    "joblib": "并行计算（scikit-learn 依赖）",
    "threadpoolctl": "线程控制（scikit-learn 依赖）",
    "colorama": "终端颜色（pytest 依赖）",
}


def default_root() -> Path:
    """由本文件位置推断工作区根目录。"""
    return Path(__file__).resolve().parent.parent


def resolve_root(root: Any = None) -> Path:
    """返回工作区根目录的绝对路径。"""
    if root is None:
        return default_root()
    return Path(root).resolve()


def _normalize_name(name: str) -> str:
    """按 PEP 503 规范化包名。"""
    return re.sub(r"[-_.]+", "-", str(name)).strip().lower()


def _requirements_names(root: Path) -> set:
    """读取 requirements.txt 中的包名集合。"""
    path = root / "requirements.txt"
    names = set()
    if not path.is_file():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[<>=!~;\[]", stripped, maxsplit=1)[0].strip()
        if name:
            names.add(_normalize_name(name))
    return names


def collect_environment(root: Any = None) -> dict:
    """收集操作系统、解释器与虚拟环境信息。"""
    root_path = resolve_root(root)
    prefix = Path(sys.prefix).resolve()
    project_venv = (root_path / ".venv").resolve()
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "venv_path": str(prefix),
        "in_venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "is_project_venv": prefix == project_venv,
        "project_root": str(root_path),
        "audit_dir": str((root_path / "audit_logs").resolve()),
    }


def collect_dependencies(root: Any = None) -> list:
    """收集已安装依赖的 名称/版本/安装位置/用途/是否在 requirements.txt。"""
    root_path = resolve_root(root)
    required = _requirements_names(root_path)
    dependencies = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        key = _normalize_name(name)
        if key in dependencies:
            continue
        dependencies[key] = {
            "name": str(name),
            "version": str(distribution.version),
            "location": str(distribution.locate_file("")),
            "purpose": PURPOSE.get(key, "间接依赖"),
            "in_requirements": key in required,
        }
    return [dependencies[key] for key in sorted(dependencies)]


def collect_outside_ops(root: Any = None) -> list:
    """只读汇总审计日志中所有 DONE/FAILED/BLOCKED 的工作区外操作。"""
    root_path = resolve_root(root)
    directory = root_path / "audit_logs"
    results = []
    if not directory.exists():
        return results
    for path in sorted(directory.glob("audit_*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("phase") not in ("DONE", "FAILED", "BLOCKED"):
                continue
            results.append(
                {
                    "seq": record.get("seq"),
                    "ts": record.get("ts"),
                    "phase": record.get("phase"),
                    "target": record.get("target"),
                    "result": record.get("result", ""),
                    "file": path.name,
                }
            )
    return results


def refresh(root: Any = None) -> dict:
    """刷新地址表的环境概览、依赖清单、工作区外操作汇总三节。"""
    root_path = resolve_root(root)
    data = log_change.load_manifest(root_path)
    data["environment"] = collect_environment(root_path)
    data["dependencies"] = collect_dependencies(root_path)
    data["outside_ops"] = collect_outside_ops(root_path)
    log_change.save_manifest(data, root_path)
    _write_md(data, root_path)
    return data


def _sha256_file(path: Path) -> Optional[str]:
    """计算文件 sha256；不存在返回 None。"""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_workspace_files(root: Path) -> Iterable[Path]:
    """遍历工作区内需要登记的文件，跳过忽略目录。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIR_NAMES]
        for filename in filenames:
            yield Path(dirpath) / filename


def verify(root: Any = None) -> tuple:
    """自检：登记文件是否存在、源码 sha256 是否一致、是否有未登记文件、审计链是否完整。"""
    root_path = resolve_root(root)
    data = log_change.load_manifest(root_path)
    problems = []
    latest: dict = {}
    for entry in data["entries"]:
        if entry.get("type") not in ("新建文件", "修改文件", "删除文件"):
            continue
        key = os.path.normcase(os.path.abspath(str(entry.get("path", ""))))
        latest[key] = entry
    for entry in latest.values():
        if entry.get("type") not in ("新建文件", "修改文件"):
            continue
        path = Path(entry.get("path", ""))
        if not path.exists():
            problems.append(f"已登记但缺失的文件：{path}")
            continue
        if path.suffix.lower() in SOURCE_SUFFIXES and entry.get("sha256"):
            actual = _sha256_file(path)
            if actual != entry["sha256"]:
                problems.append(f"sha256 不一致（内容已改变，请重新登记）：{path}")
    for path in _iter_workspace_files(root_path):
        key = os.path.normcase(os.path.abspath(str(path)))
        if key not in latest:
            problems.append(f"未登记的新文件：{path}")
    chain_ok, chain_problems = audit_log.verify_chain(root_path)
    if not chain_ok:
        problems.extend(f"审计日志：{item}" for item in chain_problems)
    return (not problems), problems


def _row(entry: dict) -> str:
    """把变更记录渲染为 markdown 表格行。"""
    def escape(text: str) -> str:
        return str(text).replace("|", "\\|")

    return "| {} | {} | {} | `{}` | {} | {} |".format(
        entry["seq"],
        entry["time"],
        entry["type"],
        escape(entry["path"]),
        escape(entry["note"]),
        escape(entry["rollback"]),
    )


def _render_md(data: dict) -> str:
    """根据 JSON 地址表重建人读版（历史记录来自 JSON，不丢条目）。"""
    lines = [
        "# 环境与变更地址表",
        "",
        "本文件由 `tools/log_change.py` 追加维护，`tools/record_env.py --refresh` 刷新固定小节。",
        "历史记录只增不减；审计日志见 `audit_logs/`，永不删除。",
        "",
        "## 变更记录",
        "",
        "| 序号 | 时间(本地) | 类型 | 绝对路径 | 说明/目的 | 回滚方式 |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(_row(entry) for entry in data.get("entries", []))

    environment = data.get("environment", {})
    lines += ["", "## 环境概览"]
    if environment:
        lines += [
            f"- 操作系统：{environment.get('os', '未知')}",
            f"- Python 解释器：`{environment.get('python_executable', '')}`",
            f"- Python 版本：{environment.get('python_version', '')}",
            f"- 虚拟环境：`{environment.get('venv_path', '')}`"
            f"（在虚拟环境内：{'是' if environment.get('in_venv') else '否'}；"
            f"是项目 .venv：{'是' if environment.get('is_project_venv') else '否'}）",
            f"- 项目根目录（工作区）：`{environment.get('project_root', '')}`",
            f"- 审计日志目录：`{environment.get('audit_dir', '')}`",
        ]
    else:
        lines.append("（待 `python tools/record_env.py --refresh` 生成）")

    lines += ["", "## 依赖清单"]
    dependencies = data.get("dependencies", [])
    if dependencies:
        lines += [
            "",
            "| 名称 | 版本 | 安装位置 | 用途 | 是否在 requirements.txt |",
            "|---|---|---|---|---|",
        ]
        for item in dependencies:
            lines.append(
                "| {} | {} | `{}` | {} | {} |".format(
                    item["name"],
                    item["version"],
                    item["location"],
                    item["purpose"],
                    "是" if item["in_requirements"] else "否",
                )
            )
    else:
        lines.append("（待 `python tools/record_env.py --refresh` 生成）")

    lines += [
        "",
        "## 运行时会写入的位置",
        "- `<项目>/data/calibration.json`",
        "- `<项目>/data/calibration.<时间戳>.bak.json`",
        "- `<项目>/data/run.log`",
        "",
        "## 工作区外操作汇总",
    ]
    outside_ops = data.get("outside_ops", [])
    if outside_ops:
        for item in outside_ops:
            lines.append(
                f"- seq={item.get('seq')} {item.get('ts')} [{item.get('phase')}] "
                f"`{item.get('target')}`：{item.get('result')}（{item.get('file')}）"
            )
    else:
        lines.append("无")
    lines += [
        "",
        "## 系统级改动",
        "无",
        "",
        "## 一键卸载步骤",
        "卸载前请保留 `audit_logs/`（审计日志永不删除）。以下命令仅写入文档，由用户手动执行。",
        "",
        "Windows（PowerShell，在项目根目录执行）：",
        "",
        "```powershell",
        "Remove-Item -Recurse -Force .venv",
        "Remove-Item -Recurse -Force .tmp",
        "Remove-Item -Recurse -Force data",
        "Remove-Item -Force main.py, config.yaml, requirements.txt, README.md",
        "Remove-Item -Recurse -Force eyemouse, tests, tools, docs",
        "# 保留 .\\audit_logs（审计日志永不删除）",
        "```",
        "",
        "macOS / Linux（在项目根目录执行）：",
        "",
        "```bash",
        "rm -rf .venv .tmp data main.py config.yaml requirements.txt README.md eyemouse tests tools docs",
        "# 保留 ./audit_logs（审计日志永不删除）",
        "```",
        "",
    ]
    return "\n".join(lines)


def _write_md(data: dict, root: Path) -> None:
    """写回人读版地址表。"""
    path = log_change.manifest_md_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_md(data), encoding="utf-8", newline="\n")


def main(argv: Optional[list] = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="环境概览/依赖清单生成与登记自检")
    parser.add_argument("--refresh", action="store_true", help="刷新地址表固定小节")
    parser.add_argument("--verify", action="store_true", help="自检登记文件、sha256 与审计链")
    parser.add_argument("--root", default=None, help="工作区根目录（默认自动推断）")
    args = parser.parse_args(argv)
    root_path = resolve_root(args.root)
    environment = collect_environment(root_path)
    if not environment["is_project_venv"]:
        print(
            "[警告] 当前 Python 不是项目 .venv 内的解释器，依赖清单可能不准确："
            f"{sys.executable}",
            file=sys.stderr,
        )
    if args.refresh:
        data = refresh(root_path)
        print(f"已刷新地址表：{log_change.manifest_md_path(root_path)}")
        print(f"依赖条数：{len(data['dependencies'])}；工作区外操作：{len(data['outside_ops'])}")
        return 0
    if args.verify:
        ok, problems = verify(root_path)
        if ok:
            print("自检通过：登记文件、sha256 与审计链均一致。")
            return 0
        print("自检发现问题：")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
