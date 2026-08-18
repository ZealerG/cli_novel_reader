"""伪装主题:伪 Vim 编辑器。

画面模拟用 vim 编辑 notes.md:
- dim 行号 gutter + 正文(缩进对齐,像 vim 的 set number)
- 文件尾的 ~ 空行(签名式 vim 元素)
- 段间随机插入 <!-- --> 注释 filler
- footer: -- INSERT -- / 写入状态行(带 % 进度)
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler

_TODOS = [
    "<!-- TODO: 补全引用出处 -->",
    "<!-- TODO: 核对术语表 -->",
    "<!-- ref: issue #%d -->",
    "<!-- 待补充示例 -->",
]


@disguise
class VimDisguise(Disguise):
    name = "vim"
    description = "伪 Vim:行号 gutter + ~ 空行 + INSERT 状态"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"vim:{self.context.get('chapter_id', '')}")

    def render(self, content: str) -> Text:
        lines = self._wrap_lines(content.splitlines(), width=72)
        out: list[Text] = []
        for ln in lines:
            out.append(Text(ln))
        # 段间注释痕迹
        if self._rng.random() < 0.15:
            todo = self._filler.choice(_TODOS)
            if "%d" in todo:
                todo = todo % self._filler.number(100, 999)
            out.append(Text(todo, style="grey37"))
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
        body: list[Text] = []
        for i, ln in enumerate(shown.plain.splitlines(), 1):
            body.append(
                Text.assemble((f"{i:>4} ", "grey37"), (ln, ""))
            )
        parts: list[Text] = [Text("\n").join(body), Text("")]
        # vim 空文件行签名
        for _ in range(3):
            parts.append(Text("~", style="grey37"))
        if paused:
            parts.append(Text("-- 已冻结 (space 继续) --", style="reverse"))
        return Text("\n").join(parts)

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        return '  1 "notes.md"  [+]'

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
        if paused:
            return "-- 已冻结 --"
        if streaming:
            return "-- INSERT --"
        pct = int(shown_count / max(total_count, 1) * 100)
        return (
            f'"notes.md" {shown_count * 8}L, {shown_count * 270}C 已写入 '
            f"· {pct}%"
        )