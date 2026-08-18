"""Textual 屏幕:书架、阅读、设置。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from cli_novel_reader.fanqie.books import BooksAPI
from cli_novel_reader.ui.disguises import get_disguise, list_disguises


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

class ReaderScreen(Screen):
    """阅读视图:正常模式 + 伪装模式,按 d 切换。

    快捷键:
    - j/↓/space  滚动下一行(正常模式)
    - n         下一章
    - p         上一章
    - d         切换伪装/正常视图
    - c         章节目录跳转
    - q         返回书架
    """

    BINDINGS = [
        Binding("n", "next_chapter", "下一章"),
        Binding("p", "prev_chapter", "上一章"),
        Binding("d", "toggle_disguise", "伪装"),
        Binding("c", "show_chapters", "目录"),
        Binding("q", "quit_reader", "书架"),
    ]

    def __init__(self, book: dict) -> None:
        super().__init__()
        self.book = book
        self.chapters: list[dict] = []
        self.chapter_idx = 0
        self.disguised = False
        self.content: dict | None = None
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("加载中...", id="chapter_title")
            with VerticalScroll(id="reader_scroll"):
                yield Static(" ", id="content")
            yield Label(" ", id="reader_status")
        yield Footer()

    async def on_mount(self) -> None:
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
        self.query_one("#chapter_title", Label).update(
            f"{self.book.get('name', '')} · {title}"
        )
        self.query_one("#content", Static).update("加载中...")
        self._update_status()

        try:
            self.content = await self.app.books_api.get_content(ch["chapter_id"])
        except Exception:
            self.content = None
            self.query_one("#content", Static).update(
                "⚠ 章节加载失败,按 r 重试或 n 跳下一章"
            )
            self._loading = False
            self._update_status()
            return

        self.render_content()
        # 滚动到顶部
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

    def render_content(self) -> None:
        paragraphs = (self.content or {}).get("paragraphs", [])
        if not paragraphs:
            self.query_one("#content", Static).update("(空章节)")
            return
        text = "\n\n".join(paragraphs)
        if self.disguised:
            disguise = get_disguise(self.app.disguise_name)
            text = disguise.render(text)
        self.query_one("#content", Static).update(text)

    def _update_status(self) -> None:
        """更新底部状态栏:章节进度 + 伪装状态。"""
        total = len(self.chapters)
        cur = self.chapter_idx + 1 if total else 0
        mode = f"[{self.app.disguise_name}]" if self.disguised else "[正常]"
        loading = " ⏳加载中" if self._loading else ""
        self.query_one("#reader_status", Label).update(
            f"  {mode}  第 {cur}/{total} 章{loading}  "
            f"n下一章 p上一章 d伪装 c目录 q书架"
        )

    def action_next_chapter(self) -> None:
        if self._loading:
            return
        if self.chapter_idx + 1 < len(self.chapters):
            self.run_worker(self.load_chapter(self.chapter_idx + 1), exclusive=True)
        else:
            self.query_one("#reader_status", Label).update(
                "  已到最后一章"
            )

    def action_prev_chapter(self) -> None:
        if self._loading:
            return
        if self.chapter_idx - 1 >= 0:
            self.run_worker(self.load_chapter(self.chapter_idx - 1), exclusive=True)
        else:
            self.query_one("#reader_status", Label).update(
                "  已到第一章"
            )

    def action_toggle_disguise(self) -> None:
        self.disguised = not self.disguised
        self.render_content()
        self._update_status()

    def action_show_chapters(self) -> None:
        """推入章节目录屏。"""
        if not self.chapters:
            return
        self.app.push_screen(ChapterListScreen(self.chapters, self.chapter_idx))

    def action_quit_reader(self) -> None:
        self.app.pop_screen()

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
