"""伪装主题:伪 Python 源文件。

小说正文伪装成模块级 docstring(绿色统一),外面是彩色代码骨架
(import / class / def / 方法)。看起来就像在读一个 Python 文件——
代码骨架是五颜六色的,小说正文只有一种颜色(绿色 docstring)。
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler


@disguise
class PythonDisguise(Disguise):
    name = "python"
    description = "伪 Python 源码:小说藏在 docstring(暗绿),外面是彩色代码"

    # docstring 用暗绿:既是 Python 字符串色,又降低对比度(但可读)
    NOVEL_STYLE: str = "rgb(108,148,108)"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"python:{self.context.get('chapter_id', '')}")

    # ── 单段正文 ───────────────────────────────────────

    def noise_line(self) -> Text:
        """Python 主题:噪声是 docstring 内的附加说明行(不能是代码)。"""
        kind = self._rng.choice(["note", "ref", "todo", "args"])
        if kind == "note":
            return Text("    Note: auto-generated, do not edit manually.", style=self.NOVEL_STYLE)
        elif kind == "ref":
            ref = self._filler.git_hash()[:8]
            return Text.assemble(("    See: ", self.NOVEL_STYLE), (f"docs/{ref}.md", self.NOVEL_STYLE))
        elif kind == "todo":
            return Text("    TODO: add type hints for all public methods.", style=self.NOVEL_STYLE)
        else:
            return Text("    Args: raw (str): input text to parse.", style=self.NOVEL_STYLE)

    def render(self, content: str) -> Text:
        """小说正文 → docstring 内容(绿色统一)。"""
        lines = self._wrap_lines(content.splitlines(), width=76)
        parts: list[Text] = []
        for ln in lines:
            if not ln.strip():
                parts.append(Text(""))
            else:
                parts.append(Text(ln, style=self.NOVEL_STYLE))
        return Text("\n").join(parts)

    # ── 整屏 frame ─────────────────────────────────────

    def frame(
        self,
        shown: Text,
        *,
        tick: int = 0,
        paused: bool = False,
        done: bool = False,
        shown_count: int = 0,
        total_count: int = 0,
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> Text:
        ts = self._filler.iso_ts()[:19]
        cls_name = self._filler.choice(
            ["StoryParser", "ContentEngine", "TextProcessor", "ChapterReader"]
        )
        parts: list[Text] = [
            # shebang + coding
            Text("#!/usr/bin/env python3", style="grey37"),
            Text("# -*- coding: utf-8 -*-", style="grey37"),
            Text("# SPDX-License-Identifier: MIT", style="grey37"),
            Text(""),
            # 模块 docstring 开头
            Text('"""', style=self.NOVEL_STYLE),
            Text.assemble(
                ("story_engine", self.NOVEL_STYLE),
                (".py", self.NOVEL_STYLE),
                ("  auto-generated parser module", self.NOVEL_STYLE),
            ),
            Text.assemble(("Updated: ", self.NOVEL_STYLE), (ts, self.NOVEL_STYLE)),
            Text(""),
            # 小说正文(docstring 内容,绿色)
            shown,
            Text(""),
            Text('"""', style=self.NOVEL_STYLE),
            Text(""),
            # imports
            Text.assemble(("import", "bold cyan"), (" logging", "")),
            Text.assemble(
                ("from", "bold cyan"), (" typing", "yellow"),
                (" import", "bold cyan"), (" Any, Optional", ""),
            ),
            Text.assemble(
                ("from", "bold cyan"), (" pathlib", "yellow"),
                (" import", "bold cyan"), (" Path", ""),
            ),
            Text(""),
            # logger
            Text.assemble(
                ("log", ""), (" = ", ""),
                ("logging", "bold cyan"), (".getLogger(", ""),
                ('"story.engine"', "green"), (")", ""),
            ),
            Text(""),
            Text(""),
            # class
            Text.assemble(
                ("class", "bold cyan"), (f" {cls_name}", "yellow"),
                (":", ""),
            ),
            Text.assemble(
                ('    """Main parser for story engine content."""', "green"),
            ),
            Text(""),
            # __init__
            Text.assemble(
                ("    def", "bold cyan"), (" __init__", "yellow"),
                ("(self, config: dict[str, Any]) -> None:", ""),
            ),
            Text.assemble(
                ("        self", ""), (".config", "yellow"),
                (" = config", ""),
            ),
            Text.assemble(
                ("        self", ""), ("._cache", "yellow"),
                (": dict[str, Any] = {}", ""),
            ),
            Text(""),
            # parse
            Text.assemble(
                ("    def", "bold cyan"), (" parse", "yellow"),
                ("(self, raw: str) -> Optional[dict]:", ""),
            ),
            Text.assemble(
                ("        if", "bold cyan"), (" not raw:", ""),
            ),
            Text.assemble(
                ("            return", "bold cyan"), (" None", "grey53"),
            ),
            Text.assemble(
                ("        return", "bold cyan"),
                (" self._normalize(raw)", ""),
            ),
            Text(""),
            # _normalize
            Text.assemble(
                ("    def", "bold cyan"), (" _normalize", "yellow"),
                ("(self, raw: str) -> dict:", ""),
            ),
            Text.assemble(
                ("        result", ""), (" = ", ""),
                ("self", ""), ("._decode", "yellow"),
                ("(raw)", ""),
            ),
            Text.assemble(
                ("        log", ""), (".debug(", ""),
                ('"parsed %d segments"', "green"),
                (", len(result))", ""),
            ),
            Text.assemble(("        return", "bold cyan"), (" result", "")),
            Text(""),
            Text.assemble(("        ...", "grey37")),
        ]
        return Text("\n").join(parts)

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        lines = 120 + (chapter_idx % 40)
        return f"story_engine.py — {lines}L"

    def footer(
        self,
        *,
        paused: bool = False,
        streaming: bool = False,
        tick: int = 0,
        shown_count: int = 0,
        total_count: int = 0,
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        branch = self._filler.choice(["main", "feat/story-engine", "dev"])
        return f"⎇ {branch}  ⚡0 ⚠0  Python 3.12  UTF-8  docstring"