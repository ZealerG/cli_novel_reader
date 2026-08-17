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
            self.query_one("#status", Label).update("未登录:按 s 进入设置粘贴 Cookie")
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
    """阅读视图:正常模式 + 伪装模式,按 d 切换。"""

    BINDINGS = [
        Binding("n", "next_chapter", "下一章"),
        Binding("p", "prev_chapter", "上一章"),
        Binding("d", "toggle_disguise", "伪装切换"),
        Binding("q", "quit_reader", "返回书架"),
    ]

    def __init__(self, book: dict) -> None:
        super().__init__()
        self.book = book
        self.chapters: list[dict] = []
        self.chapter_idx = 0
        self.disguised = False
        self.content: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("加载章节中...", id="chapter_title")
        with VerticalScroll():
            yield Static("", id="content")
        yield Footer()

    async def on_mount(self) -> None:
        self.chapters = await self.app.books_api.get_chapters(self.book["book_id"])
        if not self.chapters:
            self.query_one("#chapter_title", Label).update("⚠ 无章节数据(需登录或检查 Cookie)")
            return
        # 断点续读:优先云端进度,其次本地缓存
        idx = -1
        try:
            prog = await self.app.sync.fetch_progress(self.book["book_id"])
            if prog and int(prog.get("index", -1)) >= 0:
                idx = int(prog["index"])
        except Exception:
            pass
        if idx < 0:
            idx = self.app.store.get_progress(self.book["book_id"])
        if idx >= len(self.chapters):
            idx = 0
        await self.load_chapter(max(idx, 0))

    async def load_chapter(self, idx: int) -> None:
        if not (0 <= idx < len(self.chapters)):
            return
        self.chapter_idx = idx
        ch = self.chapters[idx]
        title = ch.get("title") or f"第{idx+1}章"
        self.query_one("#chapter_title", Label).update(f"{self.book.get('name', '')} · {title}")
        self.content = await self.app.books_api.get_content(ch["chapter_id"])
        self._render()
        # 本地 + 云端进度
        self.app.store.save_progress(self.book["book_id"], idx)
        try:
            await self.app.sync.report_progress(self.book["book_id"], ch["chapter_id"], idx)
        except Exception:
            pass

    def _render(self) -> None:
        paragraphs = (self.content or {}).get("paragraphs", [])
        text = "\n\n".join(paragraphs)
        if self.disguised:
            disguise = get_disguise(self.app.disguise_name)
            text = disguise.render(text)
        self.query_one("#content", Static).update(text)

    def action_next_chapter(self) -> None:
        if self.chapter_idx + 1 < len(self.chapters):
            self.run_worker(self.load_chapter(self.chapter_idx + 1), exclusive=True)

    def action_prev_chapter(self) -> None:
        if self.chapter_idx - 1 >= 0:
            self.run_worker(self.load_chapter(self.chapter_idx - 1), exclusive=True)

    def action_toggle_disguise(self) -> None:
        self.disguised = not self.disguised
        self._render()

    def action_quit_reader(self) -> None:
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
