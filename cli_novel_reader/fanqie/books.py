"""番茄小说搜索、章节、正文 API(去路由化,纯函数接口)。"""
from __future__ import annotations

from cli_novel_reader.fanqie.client import FanqieClient


class BooksAPI:
    """封装番茄小说内容获取 API。"""

    # 社区 API 作为正文获取的兜底源(可选配置)
    COMMUNITY_API = "http://101.35.133.34:5000"

    def __init__(self, client: FanqieClient, community_api: str = "") -> None:
        self._client = client
        self._community_api = community_api or self.COMMUNITY_API

    # ── 搜索 ───────────────────────────────────────────

    async def search(self, keyword: str, offset: int = 0) -> list[dict]:
        """搜索小说(按书名/作者)。"""
        try:
            r = await self._client.get(
                f"{self._community_api}/api/search",
                params={"key": keyword, "tab_type": 3, "offset": offset},
            )
            if r.get("code") == 200:
                raw = r.get("data", {})
                if isinstance(raw, dict):
                    tabs = raw.get("search_tabs", [])
                    books = self._extract_books(tabs)
                    return books
        except Exception:
            pass
        return []

    @staticmethod
    def _extract_books(tabs: list) -> list[dict]:
        books = []
        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            items = tab.get("data", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                bd_raw = item.get("book_data", [])
                bd = bd_raw[0] if isinstance(bd_raw, list) and bd_raw else {}
                if not isinstance(bd, dict) or not bd.get("book_id"):
                    continue
                stat = bd.get("creation_status", "")
                status_map = {"1": "连载中", "0": "已完结"}
                books.append({
                    "book_id": bd["book_id"],
                    "name": bd.get("book_name", ""),
                    "author": bd.get("author", ""),
                    "desc": bd.get("abstract", ""),
                    "thumb_url": bd.get("thumb_url", bd.get("audio_thumb_uri", "")),
                    "chapter_count": bd.get("chapter_number", ""),
                    "score": bd.get("score", ""),
                    "word_count": bd.get("word_number", 0),
                    "status": status_map.get(str(stat), ""),
                    "read_count": bd.get("read_count", 0),
                })
        return books

    # ── 章节列表 ───────────────────────────────────────

    async def get_chapters(self, book_id: str) -> list[dict]:
        """获取书籍章节目录。"""
        try:
            r = await self._client.get(
                f"{self._community_api}/api/book",
                params={"book_id": book_id},
            )
            if r.get("code") == 200:
                outer = r.get("data", {})
                inner = outer.get("data", {}) if isinstance(outer, dict) else {}
                vols = inner.get("chapterListWithVolume", [])
                result = []
                for vol in vols:
                    if isinstance(vol, list):
                        for ch in vol:
                            result.append({
                                "chapter_id": ch.get("itemId", ""),
                                "title": ch.get("title", ""),
                                "order": ch.get("realChapterOrder", ""),
                            })
                    elif isinstance(vol, dict):
                        for ch in vol.get("chapterList", []):
                            result.append({
                                "chapter_id": ch.get("chapterId", ch.get("itemId", "")),
                                "title": ch.get("chapterTitle", ch.get("title", "")),
                            })
                if result:
                    return result
                # fallback: 用 itemIds 列表
                ids = inner.get("allItemIds", [])
                return [{"chapter_id": cid, "title": f"第{i+1}章", "order": str(i+1)}
                        for i, cid in enumerate(ids)]
        except Exception:
            pass
        return []

    # ── 正文 ───────────────────────────────────────────

    async def get_content(self, chapter_id: str) -> dict | None:
        """获取章节正文。返回 {title, paragraphs, author_speak}。"""
        try:
            # 先尝试社区 API 的 raw_full 接口
            r = await self._client.get(
                f"{self._community_api}/api/raw_full",
                params={"item_id": chapter_id},
            )
            if r.get("code") == 200:
                raw = r.get("data", {})
                content_html = raw.get("content", "")
                title = raw.get("title", "")
                paragraphs = self._html_to_paragraphs(content_html)
                if paragraphs:
                    return {
                        "title": title,
                        "paragraphs": paragraphs,
                        "author_speak": raw.get("author_speak", ""),
                    }
        except Exception:
            pass

        # 兜底:content 接口
        try:
            r = await self._client.get(
                f"{self._community_api}/api/content",
                params={"tab": "小说", "item_id": chapter_id},
            )
            if r.get("code") == 200:
                text = r.get("data", {}).get("content", "")
                if text:
                    return {
                        "title": "",
                        "paragraphs": [l for l in text.split("\n") if l.strip()],
                        "author_speak": "",
                    }
        except Exception:
            pass
        return None

    @staticmethod
    def _html_to_paragraphs(html: str) -> list[str]:
        import re
        paragraphs = []
        parts = re.split(r"</?p[^>]*>", html)
        for p in parts:
            p = p.strip()
            if p and not p.startswith("<") and not p.startswith("</"):
                paragraphs.append(p)
        return paragraphs