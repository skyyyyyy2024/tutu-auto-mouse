"""地址表写入工具：把每次变更追加到 docs/CHANGE_MANIFEST.md 与 change_manifest.json。

本模块只使用 Python 标准库。所有函数支持显式传入 ``root``（工作区根目录），
便于测试使用临时目录。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import audit_log  # noqa: E402  （同目录工具模块）

VALID_TYPES = (
    "新建文件",
    "修改文件",
    "删除文件",
    "创建目录",
    "安装依赖",
    "运行命令",
    "工作区外修改",
    "系统设置(应为空)",
)
OUTSIDE_TYPE = "工作区外修改"
FIXED_HEADINGS = (
    "## 环境概览",
    "## 依赖清单",
    "## 运行时会写入的位置",
    "## 工作区外操作汇总",
    "## 系统级改动",
    "## 一键卸载步骤",
)


def default_root() -> Path:
    """由本文件位置推断工作区根目录。"""
    return Path(__file__).resolve().parent.parent


def resolve_root(root: Any = None) -> Path:
    """返回工作区根目录的绝对路径。"""
    if root is None:
        return default_root()
    return Path(root).resolve()


def manifest_md_path(root: Any = None) -> Path:
    """地址表人读版路径。"""
    return resolve_root(root) / "docs" / "CHANGE_MANIFEST.md"


def manifest_json_path(root: Any = None) -> Path:
    """地址表机器可读版路径。"""
    return resolve_root(root) / "docs" / "change_manifest.json"


def empty_manifest() -> dict:
    """空地址表结构。"""
    return {
        "entries": [],
        "environment": {},
        "dependencies": [],
        "runtime_writes": [],
        "outside_ops": [],
        "system_changes": "无",
    }


def load_manifest(root: Any = None) -> dict:
    """读取 JSON 地址表，不存在时返回空结构。"""
    path = manifest_json_path(root)
    if not path.exists():
        return empty_manifest()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    base = empty_manifest()
    base.update(data)
    return base


def save_manifest(data: dict, root: Any = None) -> None:
    """写回 JSON 地址表（机器可读版整体重写，不丢失历史条目）。"""
    path = manifest_json_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _initial_md() -> str:
    """生成地址表人读版初始内容（含固定小节）。"""
    lines = [
        "# 环境与变更地址表",
        "",
        "本文件由 `tools/log_change.py` 追加维护，历史记录只增不减。",
        "固定小节（环境概览…一键卸载步骤）由 `tools/record_env.py --refresh` 刷新。",
        "",
        "## 变更记录",
        "",
        "| 序号 | 时间(本地) | 类型 | 绝对路径 | 说明/目的 | 回滚方式 |",
        "|---|---|---|---|---|---|",
        "",
        "## 环境概览",
        "（待 `python tools/record_env.py --refresh` 生成）",
        "",
        "## 依赖清单",
        "（待 `python tools/record_env.py --refresh` 生成）",
        "",
        "## 运行时会写入的位置",
        "- `<项目>/data/calibration.json`",
        "- `<项目>/data/calibration.<时间戳>.bak.json`",
        "- `<项目>/data/run.log`",
        "",
        "## 工作区外操作汇总",
        "无",
        "",
        "## 系统级改动",
        "无",
        "",
        "## 一键卸载步骤",
        "见 README「变更与卸载」章节；卸载时必须保留 `audit_logs/`。",
        "",
    ]
    return "\n".join(lines)


def _sha256_file(path: Path) -> Optional[str]:
    """计算文件 sha256，文件不存在返回 None。"""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _escape_cell(text: str) -> str:
    """转义 markdown 表格单元格中的竖线。"""
    return str(text).replace("|", "\\|")


def _row_text(entry: dict) -> str:
    """把一条记录渲染成 markdown 表格行。"""
    return "| {} | {} | {} | `{}` | {} | {} |".format(
        entry["seq"],
        entry["time"],
        entry["type"],
        _escape_cell(entry["path"]),
        _escape_cell(entry["note"]),
        _escape_cell(entry["rollback"]),
    )


def _append_md_row(root: Path, entry: dict) -> None:
    """把新行追加到变更表末尾，且不破坏固定小节。"""
    md_path = manifest_md_path(root)
    if not md_path.exists():
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_initial_md(), encoding="utf-8", newline="\n")
    text = md_path.read_text(encoding="utf-8")
    marker = "\n" + FIXED_HEADINGS[0]
    index = text.find(marker)
    row = _row_text(entry)
    if index == -1:
        new_text = text.rstrip("\n") + "\n" + row + "\n"
    else:
        prefix = text[:index].rstrip("\n")
        suffix = text[index:]
        new_text = prefix + "\n" + row + "\n" + suffix
    md_path.write_text(new_text, encoding="utf-8", newline="\n")


def log_change(
    change_type: str,
    path: Any,
    note: str,
    rollback: str,
    root: Any = None,
    audit_seq: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> dict:
    """登记一条变更，同时写入 md 与 json。"""
    if change_type not in VALID_TYPES:
        raise ValueError(f"非法类型：{change_type}")
    root_path = resolve_root(root)
    candidate = Path(str(path))
    if candidate.is_absolute():
        absolute = str(candidate.resolve())
    else:
        absolute = str((root_path / candidate).resolve())
    if audit_log.is_outside_workspace(absolute, root_path):
        if change_type != OUTSIDE_TYPE:
            raise ValueError("工作区之外的路径，类型必须为「工作区外修改」")
        if audit_seq is None:
            raise ValueError("工作区外的变更必须提供 audit_seq（--audit-seq）")
    data = load_manifest(root_path)
    next_seq = 1
    if data["entries"]:
        next_seq = max(int(entry.get("seq", 0)) for entry in data["entries"]) + 1
    entry = {
        "seq": next_seq,
        "time": timestamp or dt.datetime.now().isoformat(timespec="seconds"),
        "type": change_type,
        "path": absolute,
        "note": note,
        "rollback": rollback,
        "audit_seq": audit_seq,
    }
    if change_type in ("新建文件", "修改文件"):
        entry["sha256"] = _sha256_file(Path(absolute))
    data["entries"].append(entry)
    save_manifest(data, root_path)
    _append_md_row(root_path, entry)
    return entry


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="追加一条变更到地址表（md 与 json 同步）")
    parser.add_argument("--type", required=True, dest="change_type", help="变更类型")
    parser.add_argument("--path", required=True, help="被变更对象的路径")
    parser.add_argument("--note", required=True, help="说明/目的")
    parser.add_argument("--rollback", required=True, help="回滚方式")
    parser.add_argument("--audit-seq", type=int, default=None, help="工作区外修改对应的审计记录 seq")
    parser.add_argument("--root", default=None, help="工作区根目录（默认自动推断）")
    args = parser.parse_args(argv)
    entry = log_change(
        args.change_type,
        args.path,
        args.note,
        args.rollback,
        root=args.root,
        audit_seq=args.audit_seq,
    )
    print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
