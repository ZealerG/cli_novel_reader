"""本地存储:阅读位置缓存,断点续读。"""
from __future__ import annotations

import json
from pathlib import Path

from cli_novel_reader.config import DATA_DIR

_STATE_FILE = DATA_DIR / "state.json"


class LocalStore:
    """本地阅读状态缓存(书籍上次阅读章节)。"""

    def __init__(self, path: Path = _STATE_FILE) -> None:
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), "utf-8")

    def get_progress(self, book_id: str) -> int:
        """返回上次阅读章节索引,无则 -1。"""
        return int(self._data.get("progress", {}).get(book_id, -1))

    def save_progress(self, book_id: str, chapter_idx: int) -> None:
        self._data.setdefault("progress", {})[book_id] = chapter_idx
        self._save()
