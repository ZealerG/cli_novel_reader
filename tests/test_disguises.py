"""伪装主题渲染测试。"""
from __future__ import annotations

import pytest
from rich.text import Text

from cli_novel_reader.ui.disguises import (
    available_disguises,
    get_disguise,
    list_disguises,
)

SAMPLE = "第一章 开端\n\n他站在窗前,看着远方的城市。\n夜色渐深。"


def test_all_disguises_registered() -> None:
    names = list_disguises()
    for required in ("vim", "ide", "logtail", "claude", "codex", "python", "gitdiff"):
        assert required in names, f"缺少主题 {required}"


def test_each_disguise_renders_content() -> None:
    for name in list_disguises():
        d = get_disguise(name)
        out = d.render(SAMPLE)
        assert isinstance(out, Text), f"{name}.render 应返回 Rich Text"
        assert len(out.plain) > 0
        # 伪装渲染必须包含原文部分内容(折行后应保留全部字符)
        assert "他站在窗前" in out.plain or "第一章" in out.plain


def test_frame_wraps_shown_content() -> None:
    """frame() 必须保留已输出的小说内容。"""
    for name in list_disguises():
        d = get_disguise(name)
        body = d.render(SAMPLE)
        frame = d.frame(body, done=True)
        assert isinstance(frame, Text)
        assert "他站在窗前" in frame.plain or "第一章" in frame.plain
        # frame 应比裸正文更长(chrome/filler 附加)
        assert len(frame.plain) >= len(body.plain)


def test_theme_chrome_lines() -> None:
    """title/footer 应返回字符串,且不泄露阅读器身份。"""
    for name in list_disguises():
        d = get_disguise(name)
        title = d.title_line(book_name="测试书", chapter_title="第一章")
        footer = d.footer(chapter_idx=0, chapter_total=100)
        assert isinstance(title, str)
        assert isinstance(footer, str)
        assert "伪装" not in title + footer
        assert "阅读" not in title + footer


def test_available_disguises_has_descriptions() -> None:
    items = available_disguises()
    assert len(items) == len(list_disguises())
    for name, desc in items:
        assert name
        assert desc


def test_render_interleaved_has_noise() -> None:
    """render_interleaved 应在段落间插入噪声行。"""
    long_content = "\n\n".join([f"段落{i}的内容文字" for i in range(12)])
    for name in list_disguises():
        d = get_disguise(name, context={"chapter_id": 12345})
        body = d.render_interleaved(long_content)
        assert isinstance(body, Text)
        assert "段落0的内容文字" in body.plain
        # 多段后应有噪声穿插(内容比纯拼接的正文长)
        plain_paras = "\n\n".join([f"段落{i}的内容文字" for i in range(12)])
        assert len(body.plain) > len(plain_paras.replace("\n", ""))


def test_unknown_disguise_raises() -> None:
    with pytest.raises(KeyError):
        get_disguise("not_exist")