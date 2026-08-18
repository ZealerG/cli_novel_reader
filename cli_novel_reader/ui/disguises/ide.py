"""伪装主题:伪 IDE 界面。

画面模拟 VS Code 编辑 + 底部终端:
- 顶部 tab 栏(notes.md 为激活 tab)
- 左侧文件树(彩色,与暗色正文形成双栏对比)
- 正文伪装成 markdown 预览块(> 引用形状,dim)
- 底部终端面板:git/pytest 活动输出
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler

_TREE = [
    ("▼", "src", "cyan", "bold"),
    ("  ", "main.py", "grey53", ""),
    ("  ", "api/", "cyan", ""),
    ("  ", "  handlers.py", "grey53", ""),
    ("  ", "  rate_limit.py", "grey53", ""),
    ("▼", "tests", "cyan", "bold"),
    ("  ", "test_worker.py", "grey53", ""),
    ("▶", "docs", "cyan", "bold"),
    ("  ", "design-notes.md", "yellow", ""),
    ("  ", "pyproject.toml", "grey53", ""),
    ("  ", "README.md", "grey53", ""),
]


@disguise
class IdeDisguise(Disguise):
    name = "ide"
    description = "伪 IDE:文件树 + md 预览 + 终端面板"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"ide:{self.context.get('chapter_id', '')}")

    def render(self, content: str) -> Text:
        lines = self._wrap_lines(content.splitlines(), width=58)
        out: list[Text] = []
        for ln in lines:
            if not ln.strip():
                out.append(Text(""))
            else:
                out.append(Text("> " + ln, style="dim"))
        if self._rng.random() < 0.2:
            out.append(Text(""))
            out.append(Text("> `TODO` 段落待整理", style="grey37"))
        return Text("\n").join(out)

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
        tabbar = Text.assemble(
            (" ─ ", "grey37"),
            ("✎ notes.md", "bold"),
            (" ✕  1: handlers.py ✕  2: tests.py ", "grey37"),
        )
        rows: list[Text] = []
        shown_lines = shown.plain.splitlines()
        for i, ln in enumerate(shown_lines):
            icon, name, color, style = _TREE[i % len(_TREE)]
            tree_cell = (icon + " " + name).ljust(14)
            rows.append(
                Text.assemble(
                    (tree_cell, color + " " + style),
                    ("│", "grey37"),
                    ("  ", ""),
                    (ln, ""),
                )
            )
        # 底部终端面板
        term = [
            Text("─" * 30, "grey37"),
            Text.assemble(("$ ", "green"), ("pytest tests/ -q", "")),
            Text("  " + self._filler.pytest_line(), "grey37"),
            Text("  " + self._filler.pytest_line(), "grey37"),
            Text(
                f"  ✓ {self._filler.number(38, 96)} passed in {self._filler.number(3, 22) / 10:.1f}s",
                "green",
            ),
        ]
        parts = [tabbar, Text.assemble(("│", "grey37")), *rows, Text(""), *term]
        if paused:
            parts.append(Text("  ⏸ 已暂停 · space 继续", style="dim"))
        return Text("\n").join(parts)

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        return f"notes.md — docs  ⏚ {10 + chapter_idx % 90}/150ms"

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
        return f"⎇ {branch}  ⚡0 ⚠0  Python 3.12  UTF-8  Markdown"