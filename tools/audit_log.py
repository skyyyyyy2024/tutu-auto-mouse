"""工作区外操作审计日志：只追加、带哈希链，禁止任何删除或清空操作。

本模块只使用 Python 标准库。所有函数都支持显式传入 ``root``（工作区根目录），
便于测试使用临时目录，避免污染真实工作区的 ``audit_logs/``。
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

ZERO_HASH = "0" * 64
AUDIT_DIR_NAME = "audit_logs"
VALID_PHASES = ("PLANNED", "DONE", "FAILED", "BLOCKED")
VALID_OPS = (
    "create",
    "write",
    "append",
    "rename",
    "move",
    "chmod",
    "config",
    "pip_install",
    "other",
)


def default_root() -> Path:
    """由本文件位置推断工作区根目录（tools/ 目录的上一级）。"""
    return Path(__file__).resolve().parent.parent


def resolve_root(root: Any = None) -> Path:
    """返回工作区根目录的绝对路径。"""
    if root is None:
        return default_root()
    return Path(root).resolve()


def audit_dir(root: Any = None) -> Path:
    """返回审计日志目录（不负责创建）。"""
    return resolve_root(root) / AUDIT_DIR_NAME


def is_outside_workspace(path: Any, root: Any = None) -> bool:
    """判断 path 经 realpath 解析后是否位于工作区之外。

    能识别符号链接逃逸与 ``..`` 逃逸；Windows 下不同驱动器视为工作区外。
    """
    workspace = os.path.realpath(str(resolve_root(root)))
    try:
        target = os.path.realpath(str(path))
    except OSError:
        target = os.path.abspath(str(path))
    if os.path.normcase(target) == os.path.normcase(workspace):
        return False
    try:
        common = os.path.commonpath([workspace, target])
    except ValueError:
        return True
    return os.path.normcase(common) != os.path.normcase(workspace)


def _read_last_record(path: Path) -> Optional[dict]:
    """读取某个日志文件的最后一条 JSON 记录，失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = [line for line in fh.read().splitlines() if line.strip()]
    except (FileNotFoundError, OSError):
        return None
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def _chain_tail(log_path: Path, directory: Path) -> tuple[str, int]:
    """返回 (上一条记录的 hash, 本条记录的 seq)。

    当天日志为空或不存在时，延续“最近一个更早日志文件”的最后 hash；
    若更早日志都是空的，则使用 64 个 0。
    """
    if log_path.exists() and log_path.stat().st_size > 0:
        last = _read_last_record(log_path)
        if last is not None:
            return str(last.get("hash", ZERO_HASH)), int(last.get("seq", 0)) + 1
    previous = ZERO_HASH
    earlier = sorted(p for p in directory.glob("audit_*.jsonl") if p.name < log_path.name)
    for candidate in reversed(earlier):
        last = _read_last_record(candidate)
        if last is not None:
            previous = str(last.get("hash", ZERO_HASH))
            break
    return previous, 1


def log(
    phase: str,
    op: str,
    target: Any,
    reason: str,
    command: str,
    result: str = "",
    ref_seq: Optional[int] = None,
    root: Any = None,
) -> dict:
    """追加一条审计记录（先算哈希链，再以追加模式写入并 fsync）。"""
    if phase not in VALID_PHASES:
        raise ValueError(f"非法 phase：{phase}")
    if op not in VALID_OPS:
        raise ValueError(f"非法 op：{op}")
    directory = audit_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()
    log_path = directory / f"audit_{now:%Y%m%d}.jsonl"
    prev_hash, seq = _chain_tail(log_path, directory)
    record: dict = {
        "seq": seq,
        "ts": now.isoformat(timespec="seconds"),
        "phase": phase,
        "op": op,
        "target": os.path.realpath(str(target)),
        "reason": reason,
        "command": command,
        "result": result,
        "ref_seq": ref_seq,
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    record["hash"] = hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(log_path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return record


def guard_outside_write(target: Any, op: str, reason: str, command: str, root: Any = None) -> int:
    """执行工作区外修改前调用：写一条 PLANNED 记录并返回其 seq。

    调用方执行完成后必须再调用 ``log("DONE"/"FAILED", ..., ref_seq=seq)`` 回写结果。
    """
    record = log("PLANNED", op, target, reason, command, root=root)
    return int(record["seq"])


def read_records(root: Any = None, date: Optional[str] = None) -> list[dict]:
    """只读地读取日志记录，供 --show 使用。"""
    directory = audit_dir(root)
    if not directory.exists():
        return []
    records: list[dict] = []
    pattern = f"audit_{date}.jsonl" if date else "audit_*.jsonl"
    for path in sorted(directory.glob(pattern)):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                if line.strip():
                    records.append(json.loads(line))
    return records


def verify_chain(root: Any = None) -> tuple[bool, list[str]]:
    """校验所有审计文件的哈希链，返回 (是否通过, 问题列表)。"""
    directory = audit_dir(root)
    problems: list[str] = []
    if not directory.exists():
        return True, problems
    expected_prev = ZERO_HASH
    for path in sorted(directory.glob("audit_*.jsonl")):
        with open(path, "r", encoding="utf-8") as fh:
            lines = [line for line in fh.read().splitlines() if line.strip()]
        for index, line in enumerate(lines, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                problems.append(f"{path.name} 第 {index} 行：JSON 解析失败")
                continue
            stored_hash = record.pop("hash", None)
            canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            expected_hash = hashlib.sha256(
                (str(record.get("prev_hash", "")) + canonical).encode("utf-8")
            ).hexdigest()
            if record.get("prev_hash") != expected_prev:
                problems.append(f"{path.name} 第 {index} 行：prev_hash 不连续")
            if stored_hash != expected_hash:
                problems.append(f"{path.name} 第 {index} 行：hash 校验失败（可能被篡改）")
            expected_prev = stored_hash if stored_hash else ZERO_HASH
    return (len(problems) == 0), problems


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口：只提供校验、展示与手动追加，绝不提供删除/清空。"""
    parser = argparse.ArgumentParser(description="工作区外操作审计日志工具（只追加、带哈希链）")
    parser.add_argument("--verify-chain", action="store_true", help="校验所有日志文件的哈希链")
    parser.add_argument("--show", action="store_true", help="只读展示日志记录")
    parser.add_argument("--date", default=None, help="配合 --show 指定日期 YYYYMMDD")
    parser.add_argument("--log", action="store_true", help="手动追加一条记录")
    parser.add_argument("--phase", default=None, help="PLANNED/DONE/FAILED/BLOCKED")
    parser.add_argument("--op", default=None, help="操作类型")
    parser.add_argument("--target", default=None, help="被操作对象的绝对路径")
    parser.add_argument("--reason", default="", help="为什么必须这样做")
    parser.add_argument("--command", default="", help="实际执行的命令描述")
    parser.add_argument("--result", default="", help="结果描述")
    parser.add_argument("--ref-seq", type=int, default=None, help="对应的 PLANNED 的 seq")
    parser.add_argument("--root", default=None, help="工作区根目录（默认自动推断）")
    args = parser.parse_args(argv)

    if args.verify_chain:
        ok, problems = verify_chain(args.root)
        if ok:
            print("哈希链校验通过。")
            return 0
        print("哈希链校验失败：")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    if args.show:
        for record in read_records(args.root, args.date):
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return 0
    if args.log:
        if not (args.phase and args.op and args.target):
            parser.error("--log 需要同时提供 --phase --op --target")
        record = log(
            args.phase,
            args.op,
            args.target,
            args.reason,
            args.command,
            args.result,
            args.ref_seq,
            args.root,
        )
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())