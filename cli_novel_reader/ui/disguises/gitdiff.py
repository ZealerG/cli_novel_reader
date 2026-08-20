"""伪装主题:伪 git diff 输出。

小说正文伪装成 diff 的绿色 + added 行,红色 - removed 行做噪声,
前后包 @@ hunk header 和文件名。看起来像在做 code review。
gitdiff 工具验证过:把任意文本格式化成 diff 输出非常自然。
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler


@disguise
class GitDiffDisguise(Disguise):
    name = "gitdiff"
    description = "伪 git diff:小说=绿色 + 行,噪声=红色 - 行"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"gitdiff:{self.context.get('chapter_id', '')}")

    def render(self, content: str) -> Text:
        lines = self._wrap_lines(content.splitlines(), width=64)
        out: list[Text] = []
        for ln in lines:
            if not ln.strip():
                out.append(Text("+"))
            else:
                out.append(Text.assemble(("+", "green"), (" " + ln, self.NOVEL_STYLE)))
        return Text("\n").join(out)

    def noise_line(self) -> Text:
        """重写:git diff 主题用红色 - 行做噪声。"""
        removed = self._filler.choice([
            "    return client.get(url)",
            "    cache.set(key, value)",
            "        raise ClientError(resp.reason)",
            "    queue.push(job, priority=0)",
            "    def parse(self, raw: str):",
            "    log.info('starting worker')",
            "        if not raw: return None",
        ])
        return Text.assemble(("-", "red"), (" " + removed, "grey53"))

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
        fname = self._filler.choice(self._filler.GIT_FILES)
        hunk_start = self._filler.number(12, 320)
        stats_add = self._filler.number(20, 180)
        stats_del = self._filler.number(3, 40)
        parts: list[Text] = [
            Text.assemble(("diff --git a/", "grey37"), (str(fname), "grey37"),
                         (" b/", "grey37"), (str(fname), "grey37")),
            Text.assemble(("index ", "grey37"), (f"{self._filler.git_hash()}..{self._filler.git_hash()}", "grey37"),
                         (" 100644", "grey37")),
            Text.assemble(("--- a/", "red"), (str(fname), "red")),
            Text.assemble(("+++ b/", "green"), (str(fname), "green")),
            Text.assemble((f"@@ -{hunk_start},7 +{hunk_start},7 @@", "cyan"),
                         (" def parse(self, raw: str):", "grey37")),
            Text(""),
            shown,
            Text(""),
            Text.assemble((f"-- \n{stats_add} insertions(+), {stats_del} deletions(-)", "grey37"),
                         ("", "")),
        ]
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
        return "git diff --stat  (working tree)"

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
        staged = self._filler.number(0, 3)
        unstaged = self._filler.number(1, 7)
        return f"⎇ {branch}  {staged} staged  {unstaged} unstaged  (REVIEW)"
