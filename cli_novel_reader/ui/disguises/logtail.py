"""伪日志终端伪装主题:小说正文伪装成程序运行日志。"""
from __future__ import annotations

import datetime as _dt

from cli_novel_reader.ui.disguises import Disguise, disguise


@disguise
class LogTailDisguise(Disguise):
    name = "logtail"
    description = "伪日志终端:正文像服务运行日志"

    def render(self, content: str) -> str:
        lines = self._wrap_lines(content.splitlines(), width=76)
        now = _dt.datetime.now()
        out = []
        for i, ln in enumerate(lines):
            ts = (now + _dt.timedelta(seconds=i)).strftime("%H:%M:%S")
            if not ln.strip():
                out.append("")
                continue
            level = "INFO"
            out.append(f"[{ts}] [worker-{i % 4}] {level} {ln}")
        return "\n".join(out)

    def status_line(self) -> str:
        return "tail -f /var/log/app.log  (Ctrl-C to stop)"
