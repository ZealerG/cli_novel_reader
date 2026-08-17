"""伪装主题渲染测试。"""
from __future__ import annotations

import pytest

from cli_novel_reader.ui.disguises import (
    available_disguises,
    get_disguise,
    list_disguises,
)

SAMPLE = "第一章 开端\n\n他站在窗前,看着远方的城市。\n夜色渐深。"


def test_all_disguises_registered() -> None:
    names = list_disguises()
    assert "vim" in names
    assert "ide" in names
    assert "logtail" in names


def test_each_disguise_renders_content() -> None:
    for name in list_disguises():
        d = get_disguise(name)
        out = d.render(SAMPLE)
        assert isinstance(out, str)
        assert len(out) > 0
        # 伪装渲染必须包含原文部分内容(折行后应保留全部字符)
        assert "他站在窗前" in out or "第一章" in out


def test_available_disguises_has_descriptions() -> None:
    items = available_disguises()
    assert len(items) == len(list_disguises())
    for name, desc in items:
        assert name
        assert desc


def test_unknown_disguise_raises() -> None:
    with pytest.raises(KeyError):
        get_disguise("not_exist")
