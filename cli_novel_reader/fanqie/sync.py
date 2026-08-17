"""进度双向同步 + 书架管理(复用 fanqie-web-reader 已验证的 API)。"""
from __future__ import annotations

import time

from cli_novel_reader.fanqie.client import FanqieClient


class ProgressSync:
    """番茄云端进度同步。

    核心 API(已验证):
    - GET  /api/reader/book/progress            → 拉取所有书进度
    - POST /api/reader/book/update_progress     → 上报当前章节进度
    - GET  /reading/bookapi/bookshelf/info/v:version/ → 书架列表
    """

    def __init__(self, client: FanqieClient) -> None:
        self._client = client

    # ── 书架 ───────────────────────────────────────────

    async def get_bookshelf(self) -> list[dict]:
        """获取云端书架(含每本书元信息)。"""
        r = await self._client.get(
            "/reading/bookapi/bookshelf/info/v:version/",
            params={"aid": "1967", "iid": "0", "version_code": "57700", "update_version_code": "57700"},
        )
        if r.get("code") != 0:
            return []
        items = r.get("data", {}).get("book_shelf_info", []) or []
        if not items:
            return []

        # 拉取书籍详情
        books_payload = []
        for b in items:
            if isinstance(b, dict) and b.get("book_id"):
                books_payload.append({"book_id": str(b["book_id"]), "item_id": "0"})

        # 批量获取详情
        detail_map = await self._fetch_multidetail(books_payload)

        progress_map = await self._get_progress_map()

        result = []
        for b in items:
            if not isinstance(b, dict):
                continue
            bid = str(b.get("book_id", ""))
            if not bid:
                continue
            info = detail_map.get(bid, {})
            prog = progress_map.get(bid, {})
            prog_item_id = prog.get("item_id", "0")
            prog_idx = prog.get("index", -1)
            prog_ts = prog.get("read_timestamp", 0)
            has_progress = bool(prog_item_id and prog_item_id != "0" and prog_ts > 0)
            result.append({
                "book_id": bid,
                "name": info.get("book_name", ""),
                "author": info.get("author", ""),
                "thumb_url": info.get("thumb_url", ""),
                "desc": info.get("abstract", ""),
                "chapter_count": int(info.get("serial_count", 0) or 0),
                "status": "连载中" if str(info.get("creation_status")) == "1" else "已完结",
                "last_read_chapter": info.get("item_show_title", "") if has_progress else "",
                "last_read_time": prog_ts if has_progress else 0,
                "read_chapter_idx": prog_idx if has_progress else -1,
                "read_item_id": prog_item_id if has_progress else "0",
            })
        return result

    async def _fetch_multidetail(self, books: list[dict]) -> dict[str, dict]:
        """批量获取书籍详情。"""
        if not books:
            return {}
        r = await self._client.post(
            "/api/bookshelf/multidetail",
            json_body={"books": books},
            csrf=True,
        )
        if r.get("code") != 0:
            return {}
        detail_map: dict[str, dict] = {}
        for item in r.get("data", {}).get("detail_list", []):
            if isinstance(item, dict) and item.get("book_id"):
                detail_map[str(item["book_id"])] = item
        return detail_map

    # ── 进度 ───────────────────────────────────────────

    async def _get_progress_map(self) -> dict[str, dict]:
        """拉取所有书的云端阅读进度。"""
        r = await self._client.get("/api/reader/book/progress")
        if r.get("code") != 0 or not isinstance(r.get("data"), list):
            return {}
        pm: dict[str, dict] = {}
        for item in r["data"]:
            bid = str(item.get("book_id", ""))
            if bid:
                pm[bid] = {
                    "item_id": str(item.get("item_id", "0")),
                    "index": int(item.get("index", 0) or 0),
                    "read_timestamp": int(item.get("read_timestamp", 0) or 0),
                }
        return pm

    async def fetch_progress(self, book_id: str) -> dict | None:
        """拉取单本书的云端进度。"""
        pm = await self._get_progress_map()
        return pm.get(book_id)

    async def report_progress(
        self,
        book_id: str,
        item_id: str,
        chapter_idx: int,
    ) -> bool:
        """上报阅读进度到番茄服务器。

        上报后手机 App 打开该书会从该章节续读。
        """
        params = {
            "book_id": book_id,
            "item_id": item_id,
            "read_progress": chapter_idx,
            "index": chapter_idx,
            "read_timestamp": str(int(time.time())),
            "genre_type": 1,
        }
        r = await self._client.post(
            "/api/reader/book/update_progress",
            params=params,
            csrf=True,
        )
        return r.get("code") == 0

    # ── 书架管理 ───────────────────────────────────────

    async def add_to_bookshelf(self, book_id: str) -> bool:
        """将书加入云端书架。"""
        params = {
            "identify_data": [{
                "book_id": book_id,
                "book_type": 0,
                "asterisked": False,
                "modify_time": int(time.time() * 1000),
            }],
            "add_book_source": 0,
        }
        r = await self._client.post(
            "/reading/bookapi/bookshelf/add/v:version/",
            params={"aid": "1967", "iid": "0", "version_code": "57700", "update_version_code": "57700"},
            json_body=params,
            csrf=True,
        )
        return r.get("code") == 0

    async def remove_from_bookshelf(self, book_id: str) -> bool:
        """从云端书架移除。"""
        params = {
            "identify_data": [{
                "book_id": book_id,
                "book_type": 0,
                "remove_type": 1,
                "modify_time": int(time.time() * 1000),
            }],
        }
        r = await self._client.post(
            "/reading/bookapi/bookshelf/delete/v:version/",
            json_body=params,
            csrf=True,
        )
        return r.get("code") == 0