"""伪装主题系统:可插拔的"看起来像在开发"的界面渲染。

设计:
- 每个伪装主题是一个 ``Disguise`` 子类,实现 ``render(content) -> str``
  把小说正文渲染成伪装后的文本(代码/日志/文件树等)。
- 主题通过装饰器 ``@disguise`` 注册,``get_disguise(name)`` 按名获取。
- 自定义主题:继承 ``Disguise`` 并注册即可,无需改动核心代码。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

_REGISTRY: dict[str, type["Disguise"]] = {}


class Disguise(ABC):
    """伪装主题基类。

    子类只需实现:
    - ``name``: 主题唯一标识(用于切换)
    - ``description``: 简短说明
    - ``render(content)``: 把正文内容渲染为伪装文本
    """

    name: str = ""
    description: str = ""

    def __init__(self, context: dict | None = None) -> None:
        self.context = context or {}

    @abstractmethod
    def render(self, content: str) -> str:
        """将小说正文渲染为伪装文本。"""

    def status_line(self) -> str:
        """伪装视图的状态栏文案(可覆写)。"""
        return ""

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
from cli_novel_reader.ui.disguises import ide, logtail, vim  # noqa: E402,F401
