"""伪装主题:OpenAI Codex CLI 会话。

画面模拟 Codex CLI 工作时序:
- 顶部 ⏺ Working + braille spinner 旋转 + turn 计数
- → read xxx 导航行,小说正文藏在"整理文档"输出块(暗色缩进)
- 段间随机穿插 shell 执行行(tests/build 结果)
- footer: esc to interrupt · token 计数 · ctx 进度条
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@disguise
class CodexDisguise(Disguise):
    name = "codex"
    description = "Codex CLI:Working spinner + turn 计数 + 进度条"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"codex:{self.context.get('chapter_id', '')}")

    # ── 单段正文 ───────────────────────────────────────

    def render(self, content: str) -> Text:
        parts: list[Text] = []
        if self._rng.random() < 0.22:
            parts.append(self._shell_block())
            parts.append(Text(""))
        lines = self._wrap_lines(content.splitlines(), width=68)
        for ln in lines:
            if not ln.strip():
                parts.append(Text(""))
            else:
                parts.append(Text("  " + ln, style="dim"))
        return Text("\n").join(parts)

    def _shell_block(self) -> Text:
        cmd = self._filler.choice(["pytest -q tests/", "npm run build", "git log --oneline -3"])
        out: list[Text] = [
            Text.assemble(("⏺ Executing ", "bold"), (str(cmd), "cyan")),
        ]
        if "pytest" in str(cmd):
            for _ in range(3):
                out.append(Text("  " + self._filler.pytest_line(), "grey37"))
            out.append(
                Text(
                    f"  ✓ {self._filler.number(38, 96)} passed in {self._filler.number(4, 38) / 10:.1f}s",
                    "green",
                )
            )
        elif "npm" in str(cmd):
            for _ in range(3):
                out.append(Text("  " + self._filler.build_line(), "grey37"))
            out.append(Text(f"  ✓ built in {self._filler.number(3, 24) / 10:.1f}s", "green"))
        else:
            for _ in range(3):
                out.append(
                    Text(f"  {self._filler.git_hash()} " + self._filler.choice(self._filler.GIT_FILES), "grey37")
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
        spin = _SPIN[tick % len(_SPIN)]
        turn = 1 + (chapter_idx % 6)  # 会话内轮次,不随章节无限增长
        parts: list[Text] = [
            Text.assemble(
                ("⏺ Working", "bold"),
                (f" (turn {turn}) ", "dim"),
                (spin, "yellow"),
                ("  ", ""),
                ("reading docs/design-notes.md", "grey37"),
            ),
            Text(f"→ edit {self._filler.choice(self._filler.GIT_FILES)}", "dim"),
            Text(""),
            shown,
        ]
        if paused:
            parts.append(Text("  ⏸ paused — space to resume", style="dim"))
        elif done:
            parts.append(Text(""))
            parts.append(
                Text(
                    f"  ✓ Done — turn {turn} · {tick * 0.9 + 3.0:.1f}s · "
                    f"{self._tokens(shown_count)} tokens",
                    "dim",
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
        return "codex ─ Working"

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
        pct = int(shown_count / max(total_count, 1) * 100)
        filled = pct // 10
        bar = "▰" * filled + "▱" * (10 - filled)
        return (
            f"esc to interrupt ·⏵⏵ {self._tokens(shown_count)} tokens ↓ "
            f"· ctx {bar} {pct}% · turn {1 + (chapter_idx % 6)}"
        )

    @staticmethod
    def _tokens(shown_count: int) -> str:
        return f"{shown_count * 340 + 800:,}"