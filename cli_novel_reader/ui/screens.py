"""Textual 屏幕:书架、阅读、设置。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from cli_novel_reader.fanqie.books import BooksAPI
from cli_novel_reader.ui.disguises import Disguise, get_disguise, list_disguises
from rich.console import Console
from rich.text import Text
from textual import events
from textual.geometry import Size


# ── 书架屏 ─────────────────────────────────────────────

class BookshelfScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.books: list[dict] = []
        self._search_mode = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="搜索小说(书名/作者),回车搜索", id="search")
        yield Label("加载书架中...", id="status")
        yield ListView(id="books")
        yield Footer()

    async def on_mount(self) -> None:
        await self._refresh()

    async def on_resume(self) -> None:
        """切回本屏时刷新(登录态可能已变)。"""
        await self._refresh()

    async def _refresh(self) -> None:
        if not self.app.client.logged_in:
            self.query_one("#status", Label).update("未登录:Ctrl+S 进入设置粘贴 Cookie")
            return
        if not self.books:
            await self._load_bookshelf()

    async def _load_bookshelf(self) -> None:
        self.query_one("#status", Label).update("同步云端书架中...")
        books = await self.app.sync.get_bookshelf()
        self.books = books
        self._search_mode = False
        self._render_books()
        self.query_one("#status", Label).update(f"云端书架: {len(books)} 本")

    def _render_books(self) -> None:
        lv = self.query_one("#books", ListView)
        lv.clear()
        for b in self.books:
            name = b.get("name") or "(未知书名)"
            status = b.get("status", "")
            last = b.get("last_read_chapter", "")
            suffix = f"  → {last}" if last else ""
            lv.append(ListItem(Label(f"{name}  [{status}]{suffix}")))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        keyword = event.value.strip()
        if not keyword:
            await self._load_bookshelf()
            return
        self.query_one("#status", Label).update(f"搜索: {keyword}")
        books = await self.app.books_api.search(keyword)
        self.books = books
        self._search_mode = True
        self._render_books()
        self.query_one("#status", Label).update(f"搜索结果: {len(books)} 本")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not (0 <= idx < len(self.books)):
            return
        book = self.books[idx]
        self.app.current_book = book
        self.app.push_screen(ReaderScreen(book))


# ── 阅读屏 ─────────────────────────────────────────────

class ReaderScroll(VerticalScroll):
    """VerticalScroll 子类:滚动位置变化时发 Scrolled 消息。

    Textual 原生 VerticalScroll 在鼠标滚轮/触控板滚动时不触发
    任何 action,导致父 Screen 无法感知滚动。此处覆写
    watch_scroll_y 在 scroll_y 变化时发消息,让 ReaderScreen
    能及时更新段评指示符。
    """

    class Scrolled(Message):
        """scroll_y 变化(键盘/鼠标/编程式滚动均触发)。"""

    def watch_scroll_y(self, old: float, new: float) -> None:
        super().watch_scroll_y(old, new)
        if round(old) != round(new):
            self.post_message(self.Scrolled())


class ReaderScreen(Screen):
    """阅读视图:正常模式 + 伪装模式,按 d 切换主题,Shift+d 开关。

    正常模式:完整正文,可上下滚动阅读。
    伪装模式:正文一次性渲染整章,包进主题工作画面(伪代码/日志/会话),
    可正常上下滚动阅读,不自动翻章。

    快捷键:
    - ↓/j       向下滚一行
    - ↑/k       向上滚一行
    - Space/PgDn  下翻一页
    - PgUp      上翻一页
    - n         下一章
    - p         上一章
    - d         切换伪装主题(python/vim/ide…)
    - Shift+d   伪装 开/关
    - f         老板键(模拟流式输出,再按恢复)
    - v         段评侧栏(开/关,自动同步当前段落,←→切换段落)
    - c         章节目录跳转
    - q         返回书架
    """

    BINDINGS = [
        Binding("n", "next_chapter", "下一章"),
        Binding("p", "prev_chapter", "上一章"),
        Binding("d", "cycle_disguise", "切主题"),
        Binding("shift+d", "toggle_disguise", "开关"),
        Binding("c", "show_chapters", "目录"),
        Binding("q", "quit_reader", "书架"),
        Binding("f", "panic", "老板键", show=False),
        Binding("v", "toggle_comments", "段评", show=False),
        Binding("left", "comments_prev_para", "上一段评", show=False),
        Binding("right", "comments_next_para", "下一段评", show=False),
        Binding("down", "scroll_down", "下滚", show=False),
        Binding("up", "scroll_up", "上滚", show=False),
        Binding("j", "scroll_down", "下滚", show=False),
        Binding("k", "scroll_up", "上滚", show=False),
        Binding("pagedown", "scroll_page_down", "下翻页", show=False),
        Binding("pageup", "scroll_page_up", "上翻页", show=False),
        Binding("space", "scroll_page_down", "下翻页", show=False),
    ]

    def __init__(self, book: dict) -> None:
        super().__init__()
        self.book = book
        self.chapters: list[dict] = []
        self.chapter_idx = 0
        self.disguised = False
        self.content: dict | None = None
        self._loading = False
        self._disguise: Disguise | None = None
        self._panic: bool = False
        self._panic_timer = None
        self._panic_idx: int = 0
        self._panic_lines: list[Text] = []
        self._comments_open: bool = False
        self._comment_stats: dict[int, int] = {}
        self._comment_paras: list[int] = []
        self._comment_para_cursor: int = 0
        self._comment_loaded_para: int = -1
        self._comment_stats_loaded: bool = False
        self._footer_cache: str = ""
        self._para_offsets: list[int] = []  # 段落视觉行偏移缓存
        self._para_offsets_width: int = 0  # 缓存时的内容宽度(变化时重算)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="reader_main"):
            with Vertical(id="reader_col"):
                yield Label("加载中...", id="chapter_title")
                with ReaderScroll(id="reader_scroll"):
                    yield Static(" ", id="content")
                yield Label(" ", id="reader_status")
            with Vertical(id="comment_sidebar"):
                yield Label("段评", id="comment_header")
                with VerticalScroll(id="comment_scroll"):
                    yield ListView(id="comment_list")
                yield Label(" ", id="comment_footer")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#comment_sidebar").display = False
        self._update_status()
        self.chapters = await self.app.books_api.get_chapters(self.book["book_id"])
        if not self.chapters:
            self.query_one("#chapter_title", Label).update("⚠ 无法获取章节数据")
            self.query_one("#content", Static).update(
                "请检查 Cookie 是否有效。\n按 q 返回书架。"
            )
            return
        # 断点续读:优先云端进度(用 item_id 反查章节序号),其次本地缓存
        idx = -1
        try:
            prog = await self.app.sync.fetch_progress(self.book["book_id"])
            if prog and prog.get("chapter_idx", -1) >= 0:
                idx = int(prog["chapter_idx"])
        except Exception:
            pass
        if idx < 0:
            idx = self.app.store.get_progress(self.book["book_id"])
        if idx >= len(self.chapters):
            idx = 0
        await self.load_chapter(max(idx, 0))

    async def load_chapter(self, idx: int) -> None:
        if self._loading or not (0 <= idx < len(self.chapters)):
            return
        self._loading = True
        self.chapter_idx = idx
        ch = self.chapters[idx]
        title = ch.get("title") or f"第{idx+1}章"
        if self.disguised:
            self._set_title_for_disguise()
        else:
            self.query_one("#chapter_title", Label).update(
                f"{self.book.get('name', '')} · {title}"
            )
        self.query_one("#content", Static).update("加载中...")
        self._update_status()

        try:
            self.content = await self.app.books_api.get_content(ch["chapter_id"], self.book["book_id"])
        except Exception:
            self.content = None
            self.query_one("#content", Static).update(
                "⚠ 章节加载失败,按 n 跳下一章"
            )
            self._loading = False
            self._update_status()
            return

        if self.disguised:
            self._render_disguise()
        else:
            self.render_content()
            scroll = self.query_one("#reader_scroll", VerticalScroll)
            scroll.scroll_home(animate=False)
        # 本地 + 云端进度
        self.app.store.save_progress(self.book["book_id"], idx)
        try:
            await self.app.sync.report_progress(
                self.book["book_id"], ch["chapter_id"], idx
            )
        except Exception:
            pass
        self._loading = False
        self._update_status()
        # 后台预加载段评统计(用于滚动时显示段落指示)
        self._comment_stats_loaded = False
        self._comment_stats = {}
        self._comment_paras = []
        self.run_worker(self._preload_comment_stats(), exclusive=True)

    def render_content(self) -> None:
        """正常模式:一次性渲染完整正文。"""
        paragraphs = (self.content or {}).get("paragraphs", [])
        if not paragraphs:
            self.query_one("#content", Static).update("(空章节)")
            return
        text = "\n\n".join(paragraphs)
        self.query_one("#content", Static).update(text)
        self._para_offsets = []
        self._para_offsets_width = 0
        self._force_relayout()

    def _force_relayout(self) -> None:
        """强制重新计算布局(Textual Static 的已知 bug:内容变化但宽度
        不变时 get_content_height 缓存不会失效,导致 virtual_size 停
        留在旧值,无法滚动到内容底部)。发一个 Resize 事件触发完整重排。
        """
        content = self.query_one("#content", Static)
        content.clear_cached_dimensions()
        size = self.app.size
        self.app.post_message(events.Resize(size, virtual_size=size))

    # ── 伪装渲染(静态) ────────────────────────────────

    def _render_disguise(self) -> None:
        """伪装模式:一次性渲染整章,包进主题画面。可正常滚动阅读。"""
        paragraphs = (self.content or {}).get("paragraphs", [])
        if not paragraphs:
            self.query_one("#content", Static).update("(空章节)")
            return
        ch = self.chapters[self.chapter_idx] if self.chapters else {}
        self._disguise = get_disguise(
            self.app.disguise_name,
            context={
                "chapter_id": ch.get("chapter_id", ""),
                "chapter_idx": self.chapter_idx,
                "book_name": self.book.get("name", ""),
            },
        )
        full = "\n\n".join(paragraphs)
        body = self._disguise.render_interleaved(full)
        if not isinstance(body, Text):
            body = Text(str(body))
        frame = self._disguise.frame(
            body,
            done=True,
            chapter_idx=self.chapter_idx,
            chapter_total=len(self.chapters),
        )
        self.query_one("#content", Static).update(frame if frame else body)
        # 缓存 footer 文本(避免滚动时重复调用 footer() 导致 PRNG 状态漂移)
        self._footer_cache = self._disguise.footer(
            chapter_idx=self.chapter_idx,
            chapter_total=len(self.chapters),
        )
        self._para_offsets = []
        self._para_offsets_width = 0
        self._set_chrome(True)
        self._set_title_for_disguise()
        self._force_relayout()
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        scroll.scroll_home(animate=False)

    def _set_chrome(self, disguised: bool) -> None:
        """伪装模式隐藏 Header/Footer(快捷键说明不能曝光)。
        段评侧栏保持可见(用户显式开启时不隐藏)。"""
        self.query_one(Header).display = not disguised
        self.query_one(Footer).display = not disguised

    def _set_title_for_disguise(self) -> None:
        """顶栏换成主题化文案。"""
        ch = self.chapters[self.chapter_idx] if self.chapters else {}
        title = ch.get("title") or f"第{self.chapter_idx + 1}章"
        line = ""
        if self._disguise is not None:
            line = self._disguise.title_line(
                book_name=self.book.get("name", ""),
                chapter_title=title,
                chapter_idx=self.chapter_idx,
                chapter_total=len(self.chapters),
            )
        if not line:
            line = f"{self.book.get('name', '')} · {title}"
        self.query_one("#chapter_title", Label).update(Text(line))

    def action_cycle_disguise(self) -> None:
        """d 键:循环切换伪装主题(未开启时自动开启)。"""
        names = list_disguises()
        if not names:
            return
        if self.disguised:
            # 已在伪装中:循环到下一主题
            cur = self.app.disguise_name
            i = names.index(cur) if cur in names else -1
            self.app.disguise_name = names[(i + 1) % len(names)]
        # 未开启伪装时:用当前主题开启,不循环
        self.disguised = True
        if self.content is not None:
            self._render_disguise()
        self._update_status()

    def action_toggle_disguise(self) -> None:
        """Shift+d 键:伪装 开/关。"""
        self.disguised = not self.disguised
        if self.disguised:
            if self.content is not None:
                self._render_disguise()
        else:
            self._disguise = None
            self._set_chrome(False)
            self.render_content()
            ch = self.chapters[self.chapter_idx] if self.chapters else {}
            title = ch.get("title") or f"第{self.chapter_idx + 1}章"
            self.query_one("#chapter_title", Label).update(
                f"{self.book.get('name', '')} · {title}"
            )
            scroll = self.query_one("#reader_scroll", VerticalScroll)
            scroll.scroll_home(animate=False)
        self._update_status()

    def _para_indicator(self) -> str:
        """生成不显眼的段评指示符,显示滚动位置对应的段落。

        格式:¶N 或 ¶N→M (M 为最近的段评段落) 或 ¶N→M♥C (C 条评论)。
        无评论统计时不显示。"""
        if not self.content or not self.content.get("paragraphs"):
            return ""
        para = self._estimate_current_para()
        if not self._comment_paras:
            return ""
        nearest = self._find_nearest_commented_para(para)
        if nearest is None:
            return ""
        count = self._comment_stats.get(nearest, 0)
        if nearest == para:
            return f"  ¶{para + 1} ♥{count}"
        else:
            return f"  ¶{para + 1}→{nearest + 1} ♥{count}"

    def _update_status(self) -> None:
        """底部状态栏:正常模式=章节进度;伪装模式=主题化 footer。

        两种模式都附带段评段落指示符(滚动时跟随更新)。
        伪装模式用缓存的 footer 文本(避免 PRNG 漂移)。
        """
        indicator = self._para_indicator()
        if self.disguised:
            label = self.query_one("#reader_status", Label)
            base = self._footer_cache or " "
            if indicator:
                label.update(Text.assemble((base, ""), (indicator, "grey53")))
            else:
                label.update(Text(base))
            return
        total = len(self.chapters)
        cur = self.chapter_idx + 1 if total else 0
        loading = " ⏳加载中" if self._loading else ""
        hint = f"n下一章 p上一章 d切主题 S+d开关 f老板键 v段评 q书架"
        self.query_one("#reader_status", Label).update(
            f"  第 {cur}/{total} 章  {loading}{indicator}  {hint}"
        )

    def action_next_chapter(self) -> None:
        if self._loading:
            return
        if self.chapter_idx + 1 < len(self.chapters):
            self.run_worker(self.load_chapter(self.chapter_idx + 1), exclusive=True)
        else:
            self.query_one("#reader_status", Label).update("  已到最后一章")

    def action_prev_chapter(self) -> None:
        if self._loading:
            return
        if self.chapter_idx - 1 >= 0:
            self.run_worker(self.load_chapter(self.chapter_idx - 1), exclusive=True)
        else:
            self.query_one("#reader_status", Label).update("  已到第一章")

    def action_show_chapters(self) -> None:
        if not self.chapters:
            return
        self.app.push_screen(ChapterListScreen(self.chapters, self.chapter_idx))

    def action_quit_reader(self) -> None:
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        """↓ / j:向下滚一行,更新段评指示。"""
        self.query_one("#reader_scroll", VerticalScroll).scroll_down(animate=False)
        self._update_status()

    def action_scroll_up(self) -> None:
        """↑ / k:向上滚一行,更新段评指示。"""
        self.query_one("#reader_scroll", VerticalScroll).scroll_up(animate=False)
        self._update_status()

    def action_scroll_page_down(self) -> None:
        """PageDown / Space:向下翻一页,更新段评指示。"""
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        scroll.scroll_relative(y=scroll.size.height - 2, animate=False)
        self._update_status()

    def action_scroll_page_up(self) -> None:
        """PageUp:向上翻一页,更新段评指示。"""
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        scroll.scroll_relative(y=-(scroll.size.height - 2), animate=False)
        self._update_status()

    def on_reader_scroll_scrolled(self, event: ReaderScroll.Scrolled) -> None:
        """鼠标滚轮/触控板滚动也触发段评指示符更新。

        VerticalScroll 原生处理鼠标滚轮但不发任何 action,
        导致 ReaderScreen 无法感知滚动。ReaderScroll 在
        scroll_y 变化时发 Scrolled 消息,此处统一更新状态栏。
        """
        self._update_status()

    # ── 段评侧栏(v:开/关+自动同步, ←→:手动切换段落) ──────────

    def _get_content_width(self) -> int:
        """获取正文渲染宽度(滚动区宽度 - 滚动条 - padding)。"""
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        w = scroll.outer_size.width
        if w <= 0:
            w = 80
        scrollbar = 1 if scroll.show_vertical_scrollbar else 0
        return max(w - scrollbar - 4, 10)  # 4 = padding 1 2 (左右各 2)

    def _compute_para_offsets(self) -> None:
        """用 Rich Text.wrap() 计算各段落的视觉行偏移(考虑终端换行+框架头/噪声)。

        Text.wrap(console, width) 返回 Lines(每个元素是一行 Text),
        行数与 Textual 渲染后的视觉行一致(含 CJK 宽度)。
        在段落文本中搜索各段首,定位到行号即为偏移。
        """
        if not self.content or not self.content.get("paragraphs"):
            self._para_offsets = []
            self._para_offsets_width = 0
            return
        paragraphs = self.content["paragraphs"]
        content_widget = self.query_one("#content", Static)
        rendered = content_widget.content
        if isinstance(rendered, Text):
            text_obj = rendered
        elif isinstance(rendered, str):
            text_obj = Text(rendered)
        else:
            text_obj = Text(str(rendered) if rendered else "")
        width = self._get_content_width()
        with open("/dev/null", "w") as devnull:
            console = Console(width=width, force_terminal=False, file=devnull)
            wrapped = text_obj.wrap(console, width)
        offsets: list[int] = []
        for p in paragraphs:
            search = p[:15] if len(p) >= 15 else p
            found = -1
            for line_idx, line in enumerate(wrapped):
                if search in line.plain:
                    found = line_idx
                    break
            offsets.append(found)
        self._para_offsets = offsets
        self._para_offsets_width = width

    def _estimate_current_para(self) -> int:
        """根据滚动位置估算用户正在阅读的段落索引(0-based)。

        用 _compute_para_offsets() 缓存的视觉行偏移做二分查找。
        若缓存过期(宽度变化)则重新计算。
        """
        if not self.content or not self.content.get("paragraphs"):
            return 0
        paragraphs = self.content["paragraphs"]
        n = len(paragraphs)
        if n <= 1:
            return 0
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        scroll_y = int(scroll.scroll_y)
        # 缓存过期(宽度变化/未计算)则重算
        cur_width = self._get_content_width()
        if cur_width != self._para_offsets_width or not self._para_offsets:
            self._compute_para_offsets()
        offsets = self._para_offsets
        if offsets and all(o >= 0 for o in offsets):
            para = 0
            for i, off in enumerate(offsets):
                if off <= scroll_y:
                    para = i
                else:
                    break
            return min(para, n - 1)
        # 回退:比例估算
        max_y = scroll.max_scroll_y
        if max_y <= 0:
            return 0
        return min(int(scroll_y / max_y * n), n - 1)

    def _find_nearest_commented_para(self, target: int) -> int | None:
        """找到离 target 最近的、有评论的段落索引。"""
        if not self._comment_paras:
            return None
        best = self._comment_paras[0]
        best_dist = abs(best - target)
        for p in self._comment_paras:
            d = abs(p - target)
            if d < best_dist:
                best = p
                best_dist = d
        return best

    def action_toggle_comments(self) -> None:
        """v 键:开/关段评侧栏。
        - 关闭时:打开并自动同步到当前阅读段落
        - 开启时:若当前阅读段落与侧栏显示的不同→重新同步;相同→关闭
        """
        if self._panic:
            return
        if not self._comments_open:
            self.run_worker(self._open_comments(), exclusive=True)
            return
        # 已开启:检查是否需要重新同步
        if self._comment_paras:
            current_para = self._estimate_current_para()
            nearest = self._find_nearest_commented_para(current_para)
            if nearest is not None:
                cur_displayed = self._comment_paras[self._comment_para_cursor]
                if nearest != cur_displayed:
                    self._comment_para_cursor = self._comment_paras.index(nearest)
                    self.run_worker(self._load_comments_for_current_para(), exclusive=True)
                    return
        # 当前段落与显示一致:关闭
        self._close_comments()

    async def _preload_comment_stats(self) -> None:
        """后台预加载本章段评统计,用于滚动时显示段落指示。"""
        if not self.chapters:
            return
        ch = self.chapters[self.chapter_idx]
        try:
            stats = await self.app.books_api.get_comment_stats(ch["chapter_id"])
        except Exception:
            return
        # 确保还在同一章(用户可能已翻章)
        if not self.chapters or self.chapters[self.chapter_idx] is not ch:
            return
        self._comment_stats = stats
        self._comment_paras = sorted(stats.keys())
        self._comment_stats_loaded = True
        self._update_status()

    async def _open_comments(self) -> None:
        """打开段评侧栏,自动同步到当前阅读段落。

        若已预加载段评统计则直接复用,无需再次请求。
        """
        sidebar = self.query_one("#comment_sidebar")
        sidebar.display = True
        self._comments_open = True
        self._para_offsets = []
        self._para_offsets_width = 0
        if not self.chapters:
            return
        ch = self.chapters[self.chapter_idx]
        self.query_one("#comment_header", Label).update(
            Text("段评 加载中...", style="bold cyan")
        )
        if not self._comment_stats_loaded:
            stats = await self.app.books_api.get_comment_stats(ch["chapter_id"])
            self._comment_stats = stats
            self._comment_paras = sorted(stats.keys())
            self._comment_stats_loaded = True
        if not self._comment_paras:
            self.query_one("#comment_header", Label).update(
                Text("段评 本章无评论", style="dim")
            )
            self.query_one("#comment_list", ListView).clear()
            return
        # 同步到当前阅读段落(找最近的有评论的段落)
        current_para = self._estimate_current_para()
        nearest = self._find_nearest_commented_para(current_para) or self._comment_paras[0]
        self._comment_para_cursor = self._comment_paras.index(nearest)
        await self._load_comments_for_current_para()

    def _close_comments(self) -> None:
        """关闭段评侧栏。"""
        self.query_one("#comment_sidebar").display = False
        self._comments_open = False
        self._para_offsets = []
        self._para_offsets_width = 0

    async def _load_comments_for_current_para(self) -> None:
        """加载当前选中段落的 top-10 评论(按点赞数排序)。"""
        if not self._comment_paras:
            return
        para = self._comment_paras[self._comment_para_cursor]
        total = self._comment_stats.get(para, 0)
        ch = self.chapters[self.chapter_idx]
        self.query_one("#comment_header", Label).update(
            Text.assemble(
                (f"段评 段落 {para + 1}", "bold cyan"),
                (f"  ({total} 条)", "dim"),
            )
        )
        self.query_one("#comment_list", ListView).clear()
        self.query_one("#comment_list", ListView).append(
            ListItem(Label(Text("加载中...", style="dim")))
        )
        comments = await self.app.books_api.get_paragraph_comments(
            ch["chapter_id"], self.book["book_id"], para, count=20,
        )
        self._comment_loaded_para = para
        lv = self.query_one("#comment_list", ListView)
        lv.clear()
        if not comments:
            lv.append(ListItem(Label(Text("无评论", style="dim"))))
        else:
            for i, c in enumerate(comments[:10]):
                text = Text.assemble(
                    (f"{c['user']}", "yellow"),
                    (f"  ❤{c['digg_count']}", "red"),
                    (f"  {c['text']}", ""),
                )
                lv.append(ListItem(Label(text)))
        # footer 提示
        idx_in_paras = self._comment_para_cursor + 1
        total_paras = len(self._comment_paras)
        self.query_one("#comment_footer", Label).update(
            Text.assemble(
                (f"段落 {idx_in_paras}/{total_paras}", "dim"),
                ("  ←→切换", "dim"),
            )
        )

    def action_comments_prev_para(self) -> None:
        """← :切换到上一个有评论的段落。"""
        if not self._comments_open or not self._comment_paras:
            return
        if self._comment_para_cursor > 0:
            self._comment_para_cursor -= 1
            self.run_worker(self._load_comments_for_current_para(), exclusive=True)

    def action_comments_next_para(self) -> None:
        """→ :切换到下一个有评论的段落。"""
        if not self._comments_open or not self._comment_paras:
            return
        if self._comment_para_cursor < len(self._comment_paras) - 1:
            self._comment_para_cursor += 1
            self.run_worker(self._load_comments_for_current_para(), exclusive=True)

    # ── 老板键(f):模拟流式输出,再按恢复 ────────────────

    def action_panic(self) -> None:
        """f 键:开启/关闭模拟流式输出。

        开启时:用当前伪装主题快速逐行输出,自动滚动,
        内容一闪而过难以看清;再次按 f 恢复原来的静态渲染和滚动位置。
        未开启伪装时自动开启。
        """
        if self._panic:
            self._panic_stop()
        else:
            self._panic_start()

    def _panic_start(self) -> None:
        """启动模拟流式输出(纯代码/噪声,不含小说内容)。"""
        if self.content is None:
            return
        # 未开启伪装时自动开启
        if not self.disguised:
            self.disguised = True
            self._render_disguise()
        if self._disguise is None:
            return
        # 保存当前滚动位置(恢复时还原)
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        self._panic_scroll_y = scroll.scroll_y
        # 生成纯代码/噪声行(不含小说内容)
        self._panic_lines = self._disguise.panic_lines(300)
        self._panic_idx = 0
        self._panic = True
        # 快速逐行输出(~30 行/秒)
        self._panic_timer = self.set_interval(1 / 30, self._panic_tick)

    def _panic_tick(self) -> None:
        """每 tick 输出更多行,自动滚到最新行。"""
        if not self._panic or not self._panic_lines:
            return
        # 每次 tick 输出 2 行(让内容快速闪过)
        step = 2
        end = min(self._panic_idx + step, len(self._panic_lines))
        shown = Text("\n").join(self._panic_lines[:end])
        self.query_one("#content", Static).update(shown)
        self._panic_idx = end
        # 自动滚到底部
        scroll = self.query_one("#reader_scroll", VerticalScroll)
        scroll.scroll_end(animate=False)
        # 输出完毕后自动循环(持续闪烁)
        if self._panic_idx >= len(self._panic_lines):
            self._panic_idx = 0

    def _panic_stop(self) -> None:
        """停止流式输出,恢复静态渲染和滚动位置。"""
        if self._panic_timer is not None:
            self._panic_timer.stop()
            self._panic_timer = None
        self._panic = False
        self._panic_lines = []
        self._panic_idx = 0
        # 恢复静态渲染
        if self.disguised and self.content is not None:
            self._render_disguise()
            # 恢复原来的滚动位置
            scroll = self.query_one("#reader_scroll", VerticalScroll)
            scroll.scroll_to(0, getattr(self, "_panic_scroll_y", 0), animate=False)

    async def on_resume(self) -> None:
        """从章节目录屏返回后,若选了新章节则跳转。"""
        target = getattr(self.app, "_chapter_jump_target", None)
        if target is not None and 0 <= target < len(self.chapters) and target != self.chapter_idx:
            self.app._chapter_jump_target = None
            await self.load_chapter(target)


# ── 章节目录屏 ─────────────────────────────────────────

class ChapterListScreen(Screen):
    """章节目录跳转屏。"""

    BINDINGS = [
        Binding("escape", "back", "返回"),
        Binding("q", "back", "返回"),
    ]

    def __init__(self, chapters: list[dict], current_idx: int) -> None:
        super().__init__()
        self.chapters = chapters
        self.current_idx = current_idx

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"共 {len(self.chapters)} 章(当前第 {self.current_idx + 1} 章)", id="ch_title")
        yield ListView(id="chapter_list")
        yield Footer()

    async def on_mount(self) -> None:
        lv = self.query_one("#chapter_list", ListView)
        for i, ch in enumerate(self.chapters):
            marker = "▶" if i == self.current_idx else " "
            title = ch.get("title") or f"第{i+1}章"
            lv.append(ListItem(Label(f"{marker} {title}")))
        # 滚动到当前章节
        if self.current_idx < len(self.chapters):
            lv.index = self.current_idx

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self.chapters):
            self.app._chapter_jump_target = idx
        self.app.pop_screen()


# ── 设置屏 ─────────────────────────────────────────────

class SettingsScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "返回书架"),
    ]

    def action_back(self) -> None:
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("== 登录 ==", classes="section")
            yield Static("", id="login_status")
            yield Input(placeholder="粘贴 fanqienovel.com 的 Cookie", id="cookie_input")
            yield Button("保存 Cookie", id="save_cookie", variant="primary")
            yield Button("清除 Cookie", id="clear_cookie")
            yield Static("", id="login_hint", classes="hint")
            yield Static("== 伪装主题 ==", classes="section")
            yield Static("", id="disguise_status")
            yield Button("切换主题", id="cycle_disguise")
        yield Footer()

    async def on_mount(self) -> None:
        self._update_login_status()
        self._update_disguise_status()

    def _update_login_status(self) -> None:
        st = self.query_one("#login_status", Static)
        st.update("已登录" if self.app.client.logged_in else "未登录")
        self.query_one("#login_hint", Static).update(
            "获取 Cookie:浏览器登录 fanqienovel.com → F12 → Network → "
            "点任意 /api 请求 → Request Headers → 复制 Cookie 值"
        )

    def _update_disguise_status(self) -> None:
        names = list_disguises()
        cur = self.app.disguise_name
        self.query_one("#disguise_status", Static).update(
            f"当前: {cur}  可选: {', '.join(names)}"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_cookie":
            cookie = self.query_one("#cookie_input", Input).value.strip()
            if cookie:
                self.app.client.save_cookie(cookie)
                self._update_login_status()
                self.query_one("#cookie_input", Input).value = ""
        elif event.button.id == "clear_cookie":
            self.app.client.delete_cookie()
            self._update_login_status()
        elif event.button.id == "cycle_disguise":
            names = list_disguises()
            if names:
                cur = self.app.disguise_name
                idx = names.index(cur) if cur in names else -1
                self.app.disguise_name = names[(idx + 1) % len(names)]
                self._update_disguise_status()
