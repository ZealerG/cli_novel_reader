"""生成各伪装主题的预览图(SVG → PNG)。

用 Rich Console(record=True) 把主题 frame 渲染成 SVG,
再用 rsvg-convert 转成 PNG,放到 docs/themes/ 供 README 引用。
"""
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.text import Text

from cli_novel_reader.ui.disguises import get_disguise, list_disguises

# 用一段真实感小说正文做样例
SAMPLE = """第一章 开端

他站在窗前,看着远方的城市。夜色渐深,街道上的灯光一盏接一盏亮起。

"你终于来了。"身后传来苍老的声音。

他转过身,看见一个白发苍苍的老人坐在阴影里,手里捧着一本翻旧的书。

"我等了很久。"老人缓缓说道,"比你能想象的更久。"

窗外的风卷起落叶,在空中打了几个旋,又散落在石板路上。城市的喧嚣仿佛隔着一层薄纱,遥远而模糊。

他沉默了片刻,终于开口:"你说的那个东西……真的存在吗?"

老人微微一笑,将书递了过来。书封上没有书名,只有一个模糊的符号,像是被岁月磨损的纹章。

"它一直都在,"老人说,"只是没有人愿意相信。"
"""

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "themes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 100  # 列数(影响 SVG 宽度)
HEIGHT = 34  # 行数(影响 SVG 高度)

# 主题顺序(README 展示顺序)
ORDER = ["python", "gitdiff", "claude", "codex", "vim", "ide", "logtail"]


def render_theme(name: str) -> Text:
    """渲染单个主题的完整 frame。"""
    d = get_disguise(name, context={
        "chapter_id": f"preview-{name}",
        "chapter_idx": 1028,
        "book_name": "诸神愚戏",
    })
    body = d.render_interleaved(SAMPLE)
    if not isinstance(body, Text):
        body = Text(str(body))
    frame = d.frame(
        body,
        done=True,
        shown_count=8,
        total_count=81,
        chapter_idx=1028,
        chapter_total=1489,
    )
    if frame is None:
        frame = body
    # 在 frame 上方加主题名标题(不在正式图里,仅用于文件名)
    return frame


def to_png(name: str, frame_text: Text) -> Path:
    """Rich Text → SVG → PNG。"""
    console = Console(
        record=True,
        width=WIDTH,
        force_terminal=True,
        color_system="truecolor",
    )
    console.print(frame_text)
    svg = console.export_svg(title=f"disguise-{name}")

    svg_path = OUT_DIR / f"{name}.svg"
    svg_path.write_text(svg, encoding="utf-8")

    png_path = OUT_DIR / f"{name}.png"
    subprocess.run(
        [
            "rsvg-convert",
            "-w", "1000",      # 输出宽度(px)
            "--background-color", "black",
            str(svg_path),
            "-o", str(png_path),
        ],
        check=True,
    )
    # 清理中间 SVG(保留以备调色)
    svg_path.unlink()
    return png_path


def main() -> None:
    for name in ORDER:
        d = get_disguise(name)
        # 确保 name 在注册表里
        frame = render_theme(name)
        png = to_png(name, frame)
        # 主题描述
        desc = d.description
        print(f"✓ {name:8s} → {png.relative_to(OUT_DIR.parent.parent)}  ({desc})")
    print(f"\n共生成 {len(ORDER)} 张图,位于 {OUT_DIR.relative_to(OUT_DIR.parent.parent)}/")


if __name__ == "__main__":
    main()