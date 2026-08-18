"""Textual 主应用:书架、阅读、伪装视图切换。"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding

from cli_novel_reader.config import DEFAULT_DISGUISE
from cli_novel_reader.fanqie import BooksAPI, FanqieClient, ProgressSync
from cli_novel_reader.storage import LocalStore
from cli_novel_reader.ui.screens import BookshelfScreen, SettingsScreen


class NovelApp(App):
    """CLI 伪装小说阅读器主应用。

    全局快捷键(``Ctrl+S`` / ``Ctrl+Q``)不会被搜索输入框拦截。
    """

    TITLE = "cli-novel-reader"
    CSS_PATH = "ui/app.tcss"

    BINDINGS = [
        Binding("ctrl+s", "toggle_settings", "书架/设置"),
        Binding("ctrl+q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.client = FanqieClient()
        self.sync = ProgressSync(self.client)
        self.books_api = BooksAPI(self.client)
        self.store = LocalStore()
        self.disguise_name: str = DEFAULT_DISGUISE
        self.current_book: dict | None = None
        self._chapter_jump_target: int | None = None

    def compose(self) -> ComposeResult:
        yield from ()

    async def on_mount(self) -> None:
        # push_screen 接受 Screen 实例,绕过 SCREENS 注册表的实例化问题
        self.push_screen(BookshelfScreen())

    def action_toggle_settings(self) -> None:
        cur = self.screen
        if isinstance(cur, SettingsScreen):
            self.pop_screen()
        else:
            self.push_screen(SettingsScreen())

    def action_quit(self) -> None:
        self.exit()

    async def on_unmount(self) -> None:
        await self.client.close()


def main() -> None:
    NovelApp().run()
