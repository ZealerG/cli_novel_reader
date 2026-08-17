"""伪 IDE 伪装主题:左侧文件树 + 右侧正文(代码样式)+ 底部终端面板。"""
from __future__ import annotations

from cli_novel_reader.ui.disguises import Disguise, disguise


@disguise
class IdeDisguise(Disguise):
    name = "ide"
    description = "伪 IDE 界面:文件树 + 代码正文 + 终端面板"

    def render(self, content: str) -> str:
        lines = self._wrap_lines(content.splitlines(), width=60)
        # 三栏布局:左文件树(固定 18 列)+ 右正文
        tree = [
            "├── src/",
            "│   ├── main.py",
            "│   ├── utils/",
            "│   │   ├── helpers.py",
            "│   │   └── parsers.py",
            "│   └── models.py",
            "├── tests/",
            "│   ├── test_main.py",
            "│   └── test_utils.py",
            "├── pyproject.toml",
            "└── README.md",
        ]
        out = []
        for i, ln in enumerate(lines):
            tree_line = tree[i % len(tree)] if i < len(tree) else " " * 18
            out.append(f"{tree_line:<18} │ {ln}")
        # 底部伪终端面板
        out.append("")
        out.append("─" * 78)
        out.append("$ ./run_tests.sh --verbose")
        out.append("  ✓ 42 passed in 0.12s")
        return "\n".join(out)

    def status_line(self) -> str:
        return "main.py — src  Python 3.12  UTF-8  Ln 1, Col 1  Spaces: 4"
