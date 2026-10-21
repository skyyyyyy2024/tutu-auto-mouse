"""受保护的删除工具：只允许删除工作区内、且不在 audit_logs/ 中的路径。

项目内任何需要删除文件/目录的代码、脚本或命令都必须调用本模块；
``safe_delete`` 会拒绝工作区外路径、``audit_logs/`` 与工作区根目录，
被拒绝时写一条 ``BLOCKED`` 审计记录，成功时登记到地址表（类型「删除文件」）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import audit_log  # noqa: E402
import log_change  # noqa: E402


def default_root() -> Path:
    """由本文件位置推断工作区根目录。"""
    return Path(__file__).resolve().parent.parent


def resolve_root(root: Any = None) -> Path:
    """返回工作区根目录的绝对路径。"""
    if root is None:
        return default_root()
    return Path(root).resolve()


def _refuse(root_path: Path, target: str, message: str) -> None:
    """写 BLOCKED 审计记录并抛出 PermissionError。"""
    audit_log.log(
        "BLOCKED",
        "other",
        target,
        "拒绝执行不安全的删除操作",
        f"safe_delete(path={target!r}, root={str(root_path)!r})",
        result=message,
        root=root_path,
    )
    raise PermissionError(message)


def safe_delete(path: Any, root: Any = None, reason: str = "工作区内受保护删除") -> str:
    """删除工作区内路径；拒绝工作区外、audit_logs/ 与工作区根目录。"""
    root_path = resolve_root(root)
    target = os.path.realpath(str(path))
    if audit_log.is_outside_workspace(target, root_path):
        _refuse(root_path, target, f"拒绝删除工作区之外的路径：{target}")
    workspace_real = os.path.realpath(str(root_path))
    audit_real = os.path.realpath(str(audit_log.audit_dir(root_path)))
    inside_audit = target == audit_real or target.startswith(audit_real + os.sep)
    if inside_audit:
        _refuse(root_path, target, f"拒绝删除 audit_logs/ 或其内部内容：{target}")
    if os.path.normcase(target) == os.path.normcase(workspace_real):
        _refuse(root_path, target, f"拒绝删除工作区根目录：{target}")
    if not os.path.lexists(target):
        raise FileNotFoundError(f"待删除路径不存在：{target}")
    if os.path.isdir(target) and not os.path.islink(target):
        shutil.rmtree(target)
    else:
        os.remove(target)
    entry = log_change.log_change(
        "删除文件",
        target,
        reason,
        "无法恢复（已删除）",
        root=root_path,
    )
    print(f"已删除：{target}（已登记地址表 seq={entry['seq']}）")
    return target


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="受保护的删除（拒绝工作区外与 audit_logs/）")
    parser.add_argument("path", help="待删除路径")
    parser.add_argument("--root", default=None, help="工作区根目录（默认自动推断）")
    parser.add_argument("--reason", default="工作区内受保护删除", help="删除原因")
    args = parser.parse_args(argv)
    safe_delete(args.path, root=args.root, reason=args.reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())