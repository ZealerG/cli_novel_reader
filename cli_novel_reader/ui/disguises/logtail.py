"""伪装主题:伪生产日志终端(tail -f 结构化日志)。

画面模拟 kubectl logs -f 结构化服务日志:
- 小说正文伪装成 DEBUG story.engine 日志的 msg="..." 字段(暗色)
- 前置 INFO/WARN/ERROR 彩色活动行,眼睛先被它们吸引
- 每 tick 尾部新增随机活动日志,屏幕持续"活着"
"""
from __future__ import annotations

from rich.text import Text

from cli_novel_reader.ui.disguises import Disguise, disguise
from cli_novel_reader.ui.disguises.noise import Filler


@disguise
class LogTailDisguise(Disguise):
    name = "logtail"
    description = "伪生产日志:t_stamp + 结构化 msg + 活动行"

    def __init__(self, context: dict | None = None) -> None:
        super().__init__(context)
        self._filler = Filler(f"logtail:{self.context.get('chapter_id', '')}")

    def render(self, content: str) -> Text:
        # 段落正文(噪声由 render_interleaved 统一穿插)
        out: list[Text] = []
        lines = self._wrap_lines(content.splitlines(), width=46)
        for ln in lines:
            if not ln.strip():
                out.append(Text(""))
                continue
            out.append(
                Text.assemble(
                    (self._filler.iso_ts() + "  ", "grey37"),
                    ("DEBUG ", "grey37"),
                    ("story.engine ", "cyan"),
                    ("worker=3 ", "grey37"),
                    (f'msg="{ln}"', self.NOVEL_STYLE),
                )
            )
        return Text("\n").join(out)

    def _active_line(self, level: str) -> Text:
        styles = {"INFO": "grey53", "WARN": "yellow", "ERROR": "red"}
        body = self._filler.worker_line()
        # worker_line 格式: ts + 2空格 + LEVEL + 2空格 + mid + 2空格 + metric
        head, _orig_level, tail = body.split("  ", 2)
        return Text.assemble(
            (f"{head}  {level:<5} ", styles[level]),
            (tail.strip(), styles[level]),
        )

    def noise_line(self) -> Text:
        """LogTail 主题:噪声是活动日志行。"""
        level = self._filler.choice(["INFO", "INFO", "INFO", "WARN"])
        return self._active_line(level)

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
        head = Text.assemble(
            ("==> ", "bold"),
            ("/var/log/story/worker-3.log", "bold"),
            (" <==  ", ""),
            (f"跟随新增… {tick}", "grey37"),
        )
        parts = [head, Text.assemble(("┌─", "grey37")), shown]
        # 尾部持续滚入活动日志(每 tick 变化)
        fresh = [
            self._active_line(
                self._filler.choice(["INFO", "INFO", "INFO", "WARN"])
            ),
            self._active_line("INFO"),
        ]
        parts.append(Text(""))
        parts.extend(fresh)
        if paused:
            parts.append(Text("  ⏸ 已暂停 · space 继续", style="dim"))
        elif done:
            parts.append(Text("  (tail 等待新日志…)", style="grey37"))
        return Text("\n").join(parts)

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        return "kubectl logs -f deploy/story-worker --since=4h"

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
        conn = self._filler.number(2, 9)
        qps = self._filler.number(83, 421)
        return f"·  conn={conn}  qps={qps}  p95={self._filler.number(2, 40)}ms  ·  (Ctrl-C 退出)"