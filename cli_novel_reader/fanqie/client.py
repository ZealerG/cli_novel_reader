"""番茄小说 HTTP 客户端:Cookie 管理、请求封装。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from cli_novel_reader.config import COOKIE_FILE

WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)
FANQIE_BASE = "https://fanqienovel.com"


class FanqieClient:
    """封装番茄小说网页 API 的 HTTP 客户端。

    核心职责:
    - Cookie 持久化(登录态)
    - CSRF token 提取
    - 统一请求头拼接
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )
        self._cookie: str = ""
        self._csrf_token: str = ""
        self._load_cookie()

    # ── Cookie 持久化 ──────────────────────────────────

    def _load_cookie(self) -> None:
        if COOKIE_FILE.exists():
            try:
                raw = COOKIE_FILE.read_text("utf-8").strip()
                data = json.loads(raw) if raw.startswith("{") else {"cookie": raw}
                self._cookie = data.get("cookie", "")
                self._csrf_token = self._extract_csrf(self._cookie)
            except Exception:
                pass

    def save_cookie(self, cookie: str) -> None:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps({"cookie": cookie}, ensure_ascii=False), "utf-8")
        self._cookie = cookie
        self._csrf_token = self._extract_csrf(cookie)

    def delete_cookie(self) -> None:
        if COOKIE_FILE.exists():
            COOKIE_FILE.unlink()
        self._cookie = ""
        self._csrf_token = ""

    @property
    def logged_in(self) -> bool:
        return bool(self._cookie)

    # ── CSRF ───────────────────────────────────────────

    @staticmethod
    def _extract_csrf(cookie: str) -> str:
        for part in cookie.split(";"):
            kv = part.strip().split("=", 1)
            if len(kv) == 2 and kv[0].strip() == "passport_csrf_token":
                return kv[1].strip()
        return ""

    # ── 请求头 ─────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "User-Agent": WEB_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://fanqienovel.com/",
            "Content-Type": "application/json",
        }
        if self._cookie:
            h["Cookie"] = self._cookie
        return h

    def _csrf_headers(self) -> dict[str, str]:
        h = self._headers()
        h["x-secsdk-csrf-token"] = self._csrf_token
        h["origin"] = "https://fanqienovel.com"
        return h

    # ── 通用请求 ───────────────────────────────────────

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{FANQIE_BASE}{path}" if not path.startswith("http") else path
        r = await self._client.get(url, headers=self._headers(), params=params)
        return r.json()

    async def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        csrf: bool = False,
    ) -> dict[str, Any]:
        url = f"{FANQIE_BASE}{path}" if not path.startswith("http") else path
        headers = self._csrf_headers() if csrf else self._headers()
        r = await self._client.post(url, headers=headers, params=params, json=json_body)
        return r.json()

    # ── 资源清理 ───────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()