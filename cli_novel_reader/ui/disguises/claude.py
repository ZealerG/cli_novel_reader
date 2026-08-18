"""伪装主题:Claude Code 会话。

画面模拟一次 Claude Code 交互:
- 顶部 ⏺ Bash(...) 命令 + 真实感的输出块
- 小说正文藏在 "cat docs/design-notes.md" 的输出块里(暗色缩进行)
- 段间随机穿插 ⏺ Edit + 绿/红 diff 块
- 底部 footer: ⏵⏵ esc to interrupt · token 计数
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler

_PY_EDIT = [
    ("-", "    if resp.status != 200:", "red"),
    ("+", "    if resp and resp.status != 200:", "green"),
    (" ", "        raise ClientError(resp.reason)", ""),
    ("-", "    cache.set(key, value)", "red"),
    ("+", "    cache.set(key, value, ttl=3600)", "green"),
    (" ", "    return parser.parse(body)", ""),
    ("+", "    metrics.increment('parse.ok')", "green"),
]


@disguise
class ClaudeDisguise(Disguise):
    name = "claude"
    description = "Claude Code 会话:tool call + 输出块 + diff"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"{self.name}:{self.context.get('chapter_id', '')}")

    # ── 单段正文 ───────────────────────────────────────

    def render(self, content: str) -> Text:
        # 约 1/5 概率在段落前插一个 diff 块(tool call 痕迹)
        parts: list[Text] = []
        if self._rng.random() < 0.18:
            parts.append(self._diff_block())
            parts.append(Text(""))
        lines = self._wrap_lines(content.splitlines(), width=66)
        for ln in lines:
            if not ln.strip():
                parts.append(Text(""))
            else:
                parts.append(Text("   " + ln, style="dim"))
        return Text("\n").join(parts)

    def _diff_block(self) -> Text:
        fname = self._filler.choice(self._filler.GIT_FILES)
        start = self._filler.number(12, 320)
        out: list[Text] = [
            Text.assemble(("  ⏺ ", "bold cyan"), ("Edit ", ""), (str(fname), "bold")),
            Text(f"    @@ -{start},7 +{start},7 @@", style="grey37"),
        ]
        for prefix, code, style in _PY_EDIT:
            out.append(
                Text.assemble((f"    {prefix} ", style or ""), (code, style or "grey37"))
            )
        return Text("\n").join(out)

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
        parts: list[Text] = [
            Text.assemble(
                ("  ⏺ ", "bold cyan"),
                ("Bash(cat docs/design-notes.md)", "bold"),
                ("   ", ""),
                (f"·  {tick * 0.8 + 0.4:.1f}s", "grey37"),
            ),
            Text("   ⎿  M docs/design-notes.md   (working tree clean)", "grey37"),
            Text(""),
            shown,
        ]
        if paused:
            parts.append(Text("  ⏸ 已暂停 · space 继续", style="dim"))
        elif done:
            parts.append(Text(""))
            parts.append(
                Text(
                    f"  ✓ 任务完成 · {tick * 1.7:.1f}s · "
                    f"{self._tokens(shown_count)} tokens · {total_count} 个段落已处理",
                    style="dim",
                )
            )
        return Text("\n").join(parts)

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        return "✻ ~/work/docs — Claude Code"

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
        state = "⏸" if paused else ""
        return (
            f"{state}⏵⏵ esc to interrupt  ·  ❯ {self._tokens(shown_count)} tokens "
            f"·  model claude-4.5"
        )

    @staticmethod
    def _tokens(shown_count: int) -> str:
        return f"{shown_count * 540 + 1200:,}"