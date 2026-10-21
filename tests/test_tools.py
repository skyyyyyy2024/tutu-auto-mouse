"""地址表工具与 record_env 自检测试（全部使用 tmp_path 作为 root）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import audit_log  # noqa: E402
import log_change  # noqa: E402
import record_env  # noqa: E402


def init_workspace(tmp_path: Path) -> None:
    """建立一个最小但登记完整的工作区（含地址表自身）。"""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "audit_logs").mkdir(exist_ok=True)
    log_change.log_change("创建目录", str(tmp_path / "docs"), "文档目录", "删除", root=tmp_path)
    log_change.log_change(
        "新建文件", str(tmp_path / "docs" / "CHANGE_MANIFEST.md"), "地址表人读", "删除", root=tmp_path
    )
    log_change.log_change(
        "新建文件",
        str(tmp_path / "docs" / "change_manifest.json"),
        "地址表机器可读",
        "删除",
        root=tmp_path,
    )


def test_log_change_seq_increments_and_syncs_md(tmp_path):
    init_workspace(tmp_path)
    entry = log_change.log_change("新建文件", str(tmp_path / "a.py"), "示例", "删除", root=tmp_path)
    assert entry["seq"] == 4
    data = log_change.load_manifest(tmp_path)
    assert [item["seq"] for item in data["entries"]] == [1, 2, 3, 4]
    md = log_change.manifest_md_path(tmp_path).read_text(encoding="utf-8")
    assert "| 4 |" in md
    for heading in log_change.FIXED_HEADINGS:
        assert heading in md
    assert md.index("| 4 |") < md.index("## 环境概览")


def test_log_change_relative_path_becomes_absolute(tmp_path):
    init_workspace(tmp_path)
    entry = log_change.log_change("创建目录", "subdir", "相对路径", "删除", root=tmp_path)
    assert os.path.isabs(entry["path"])
    assert entry["path"] == os.path.abspath(str(tmp_path / "subdir"))


def test_log_change_outside_path_requires_audit_seq(tmp_path):
    init_workspace(tmp_path)
    outside = tmp_path.parent / "elsewhere" / "f.txt"
    with pytest.raises(ValueError):
        log_change.log_change("新建文件", str(outside), "外部", "删除", root=tmp_path)
    with pytest.raises(ValueError):
        log_change.log_change("工作区外修改", str(outside), "外部", "删除", root=tmp_path)
    entry = log_change.log_change(
        "工作区外修改", str(outside), "外部", "删除", root=tmp_path, audit_seq=5
    )
    assert entry["audit_seq"] == 5


def test_record_env_verify_clean(tmp_path):
    init_workspace(tmp_path)
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n", encoding="utf-8")
    log_change.log_change("新建文件", str(source), "示例源码", "删除", root=tmp_path)
    ok, problems = record_env.verify(tmp_path)
    assert ok, problems


def test_record_env_verify_reports_missing_file(tmp_path):
    init_workspace(tmp_path)
    log_change.log_change("新建文件", str(tmp_path / "ghost.py"), "缺失文件", "删除", root=tmp_path)
    ok, problems = record_env.verify(tmp_path)
    assert not ok
    assert any("缺失" in problem for problem in problems)


def test_record_env_verify_reports_unregistered_file(tmp_path):
    init_workspace(tmp_path)
    (tmp_path / "extra.py").write_text("y = 2\n", encoding="utf-8")
    ok, problems = record_env.verify(tmp_path)
    assert not ok
    assert any("未登记" in problem for problem in problems)


def test_record_env_verify_reports_sha256_mismatch(tmp_path):
    init_workspace(tmp_path)
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n", encoding="utf-8")
    log_change.log_change("新建文件", str(source), "示例源码", "删除", root=tmp_path)
    source.write_text("x = 2\n", encoding="utf-8")
    ok, problems = record_env.verify(tmp_path)
    assert not ok
    assert any("sha256" in problem for problem in problems)


def test_record_env_verify_ignores_audit_logs(tmp_path):
    init_workspace(tmp_path)
    audit_log.log(
        "DONE",
        "write",
        str(tmp_path.parent / "outside.txt"),
        "外部写入",
        "cmd",
        result="完成",
        root=tmp_path,
    )
    ok, problems = record_env.verify(tmp_path)
    assert ok, problems


def test_record_env_cli_verify_exit_codes(tmp_path):
    init_workspace(tmp_path)
    assert record_env.main(["--verify", "--root", str(tmp_path)]) == 0
    (tmp_path / "extra.py").write_text("z = 3\n", encoding="utf-8")
    assert record_env.main(["--verify", "--root", str(tmp_path)]) == 1


def test_record_env_refresh_updates_sections(tmp_path):
    init_workspace(tmp_path)
    data = record_env.refresh(tmp_path)
    assert data["environment"]["project_root"] == str(tmp_path.resolve())
    assert data["dependencies"]
    md = log_change.manifest_md_path(tmp_path).read_text(encoding="utf-8")
    assert "## 环境概览" in md
    assert "## 依赖清单" in md
    assert "## 工作区外操作汇总" in md
    assert "## 系统级改动" in md
    assert "## 一键卸载步骤" in md
