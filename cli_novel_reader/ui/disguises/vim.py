"""伪 Vim 编辑器伪装主题:小说正文以等宽代码形式呈现。"""
from __future__ import annotations

from cli_novel_reader.ui.disguises import Disguise, disguise


@disguise
class VimDisguise(Disguise):
    name = "vim"
    description = "伪 Vim 编辑器:正文像源码,带行号与状态栏"

    def render(self, content: str) -> str:
        lines = self._wrap_lines(content.splitlines(), width=70)
        # 加上行号,像 vim 的 :set number
        width = len(str(len(lines)))
        numbered = [f"{i+1:>{width}} {ln}" for i, ln in enumerate(lines)]
        return "\n".join(numbered)

    def status_line(self) -> str:
        return "main.py [Python] - 142/142L  12:34:56"
