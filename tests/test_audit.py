"""审计日志与受保护删除测试（全部使用 tmp_path 作为 root，不写入真实 audit_logs/）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import audit_log  # noqa: E402
import log_change  # noqa: E402
import safe_delete  # noqa: E402


def test_log_appends_and_chain_is_continuous(tmp_path):
    first = audit_log.log("PLANNED", "create", tmp_path / "x", "测试", "cmd", root=tmp_path)
    second = audit_log.log(
        "DONE",
        "create",
        tmp_path / "x",
        "测试",
        "cmd",
        result="ok",
        ref_seq=first["seq"],
        root=tmp_path,
    )
    records = audit_log.read_records(tmp_path)
    assert len(records) == 2
    assert [record["seq"] for record in records] == [1, 2]
    assert second["prev_hash"] == first["hash"]
    ok, problems = audit_log.verify_chain(tmp_path)
    assert ok, problems


def test_tampered_record_fails_chain(tmp_path):
    audit_log.log("PLANNED", "create", tmp_path / "x", "原始原因", "cmd", root=tmp_path)
    log_file = next((tmp_path / "audit_logs").glob("audit_*.jsonl"))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["reason"] = "被篡改"
    lines[0] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, problems = audit_log.verify_chain(tmp_path)
    assert not ok
    assert problems
    assert audit_log.main(["--verify-chain", "--root", str(tmp_path)]) == 1


def test_guard_outside_write_returns_planned_seq(tmp_path):
    target = tmp_path.parent / "outside.bin"
    seq = audit_log.guard_outside_write(target, "write", "必须写入外部", "cmd", root=tmp_path)
    done = audit_log.log(
        "DONE",
        "write",
        target,
        "必须写入外部",
        "cmd",
        result="完成",
        ref_seq=seq,
        root=tmp_path,
    )
    assert done["ref_seq"] == seq
    records = audit_log.read_records(tmp_path)
    assert records[0]["phase"] == "PLANNED"
    assert records[1]["phase"] == "DONE"
    assert records[1]["ref_seq"] == records[0]["seq"]


def test_is_outside_workspace_detects_dotdot_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert audit_log.is_outside_workspace(workspace / "a.txt", root=workspace) is False
    assert audit_log.is_outside_workspace(workspace / ".." / "escape.txt", root=workspace) is True


def test_is_outside_workspace_detects_symlink_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不允许创建符号链接")
    assert audit_log.is_outside_workspace(link / "file.txt", root=workspace) is True


def test_safe_delete_rejects_outside_path(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    with pytest.raises(PermissionError):
        safe_delete.safe_delete(outside, root=workspace)
    records = audit_log.read_records(workspace)
    assert records and records[-1]["phase"] == "BLOCKED"
    assert outside.exists()


def test_safe_delete_rejects_audit_logs_and_root(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    audit_dir = workspace / "audit_logs"
    audit_dir.mkdir()
    inside = audit_dir / "audit_20250101.jsonl"
    inside.write_text("", encoding="utf-8")
    with pytest.raises(PermissionError):
        safe_delete.safe_delete(audit_dir, root=workspace)
    with pytest.raises(PermissionError):
        safe_delete.safe_delete(inside, root=workspace)
    with pytest.raises(PermissionError):
        safe_delete.safe_delete(workspace, root=workspace)
    assert inside.exists()


def test_safe_delete_removes_and_registers(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = workspace / "victim.txt"
    victim.write_text("bye", encoding="utf-8")
    result = safe_delete.safe_delete(victim, root=workspace)
    assert result == os.path.realpath(str(victim))
    assert not victim.exists()
    data = log_change.load_manifest(workspace)
    assert data["entries"][-1]["type"] == "删除文件"


def test_audit_module_exposes_no_delete_api():
    forbidden = ("delete", "clear", "truncate", "remove", "purge", "shred")
    public = [name for name in dir(audit_log) if not name.startswith("_")]
    assert not [
        name for name in public if any(word in name.lower() for word in forbidden)
    ]
