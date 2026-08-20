"""伪装主题系统:可插拔的"看起来像在开发"的界面渲染。

设计:
- 每个伪装主题是一个 ``Disguise`` 子类,实现 ``render(content) -> Text``
  把小说正文渲染成伪装文本(Rich Text,支持 dim/彩色)。
- ``frame()`` 钩子把已输出的正文包进主题化"工作画面":
  spinner、tool call 卡片、diff 块、token 计数等,让屏幕看起来
  像有 agent / 进程正在运行。
- 主题通过装饰器 ``@disguise`` 注册,``get_disguise(name)`` 按名获取。
- 自定义主题:继承 ``Disguise`` 并注册即可,无需改动核心代码。
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod

from rich.text import Text

_REGISTRY: dict[str, type["Disguise"]] = {}


class Disguise(ABC):
    """伪装主题基类。

    必实现:
    - ``name``: 主题唯一标识(用于切换)
    - ``description``: 简短说明
    - ``render(content)``: 把一段正文渲染为伪装文本

    可覆写钩子:
    - ``frame(shown, ...)``: 把已输出的正文包进主题画面(默认原样)
    - ``title_line(...)``: 伪装视图顶栏文案(默认空)
    - ``footer(...)``: 伪装视图底部状态栏(默认空)
    - ``noise_line()``: 返回一行彩色工作噪声(用于段落间穿插)
    """

    name: str = ""
    description: str = ""

    # CloakingNote 研究发现:显式低对比度色比 dim 更可靠
    # (dim 在浅色终端会失效);用中等灰:足够阅读但不如噪声醒目
    NOVEL_STYLE: str = "rgb(130,130,130)"
    # 噪声行用高对比度,吸引注意力(信噪比原理)
    NOISE_STYLE: str = "bold"
    # 段落间噪声插入概率(每隔 N 段插一行)
    NOISE_EVERY: int = 4

    def __init__(self, context: dict | None = None) -> None:
        self.context = context or {}
        # 同章节内噪声序列稳定,跨章节不同(用章节 id 做种子)
        seed = self.context.get("chapter_id") or self.name
        self._rng = random.Random(seed)

    @abstractmethod
    def render(self, content: str) -> Text:
        """将一段正文渲染为伪装文本。"""

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
        """把当前已输出的正文包进主题化画面。默认原样返回。"""
        return shown

    def title_line(
        self,
        *,
        book_name: str = "",
        chapter_title: str = "",
        chapter_idx: int = 0,
        chapter_total: int = 0,
    ) -> str:
        """伪装视图顶栏文案。返回空串则退回默认标题。"""
        return ""

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
        """伪装视图底部状态栏。返回空串则显示空白。"""
        return ""

    def noise_line(self) -> Text:
        """一行彩色工作噪声,用于段落间穿插。默认从 Filler 取。"""
        from cli_novel_reader.ui.disguises.noise import Filler
        if not hasattr(self, "_filler"):
            self._filler = Filler(f"{self.name}:{self.context.get('chapter_id', '')}")
        kind = self._rng.choice(["git", "pytest", "build", "http", "docker", "cargo", "npm"])
        if kind == "git":
            return Text(self._filler.git_line(), style="green")
        elif kind == "pytest":
            return Text(self._filler.pytest_line(), style="green")
        elif kind == "build":
            return Text(self._filler.build_line(), style="cyan")
        elif kind == "http":
            return Text(self._filler.http_line(), style="yellow")
        elif kind == "docker":
            return Text(self._filler.docker_line(), style="cyan")
        elif kind == "cargo":
            return Text(self._filler.cargo_line(), style="green")
        else:
            return Text(self._filler.npm_line(), style="cyan")

    def panic_lines(self, count: int = 200) -> list[Text]:
        """生成纯噪声行(不含小说内容),用于老板键流式输出。

        子类可覆写以匹配主题风格;默认生成随机代码行 + 构建日志混合。
        """
        from cli_novel_reader.ui.disguises.noise import Filler
        if not hasattr(self, "_filler"):
            self._filler = Filler(f"{self.name}:{self.context.get('chapter_id', '')}")
        lines: list[Text] = []
        for _ in range(count):
            kind = self._rng.choice(["code", "code", "code", "pytest", "git", "build", "log"])
            if kind == "code":
                lines.append(Text(self._filler.code_line(), style="green"))
            elif kind == "pytest":
                lines.append(Text(self._filler.pytest_line(), style="green"))
            elif kind == "git":
                lines.append(Text(self._filler.git_line(), style="cyan"))
            elif kind == "build":
                lines.append(Text(self._filler.build_line(), style="cyan"))
            else:
                lines.append(Text(self._filler.worker_line(), style="grey53"))
        return lines

    def render_interleaved(self, content: str) -> Text:
        """渲染正文 + 段落间穿插噪声行(信噪比原理)。"""
        paragraphs = content.split("\n\n")
        parts: list[Text] = []
        since_noise = 0
        for para in paragraphs:
            para = para.strip()
            if not para:
                parts.append(Text(""))
                continue
            rendered = self.render(para)
            if not isinstance(rendered, Text):
                rendered = Text(str(rendered))
            parts.append(rendered)
            parts.append(Text(""))
            since_noise += 1
            if since_noise >= self.NOISE_EVERY and self._rng.random() < 0.7:
                parts.append(self.noise_line())
                parts.append(Text(""))
                since_noise = 0
        return Text("\n").join(parts)

    # ── 便捷工具 ───────────────────────────────────────

    @staticmethod
    def _wrap_lines(lines: list[str], width: int = 78) -> list[str]:
        """按等宽宽度折行,保持段落结构。"""
        out: list[str] = []
        for line in lines:
            if not line.strip():
                out.append("")
                continue
            while len(line) > width:
                out.append(line[:width])
                line = line[width:]
            out.append(line)
        return out


def disguise(cls: type[Disguise]) -> type[Disguise]:
    """主题注册装饰器。"""
    if not cls.name:
        raise ValueError(f"Disguise {cls.__name__} 缺少 name 属性")
    _REGISTRY[cls.name] = cls
    return cls


def get_disguise(name: str, context: dict | None = None) -> Disguise:
    """按名称获取伪装主题实例。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"未知伪装主题: {name},可用: {list(_REGISTRY)}")
    return cls(context)


def list_disguises() -> list[str]:
    """列出所有已注册主题名。"""
    return sorted(_REGISTRY)


def available_disguises() -> list[tuple[str, str]]:
    """列出所有已注册主题 (name, description)。"""
    return [(n, _REGISTRY[n].description) for n in list_disguises()]


# 导入内置主题,触发注册(装饰器)。自定义主题只需在入口导入即可。
from cli_novel_reader.ui.disguises import claude, codex, gitdiff, ide, logtail, python, vim  # noqa: E402,F401