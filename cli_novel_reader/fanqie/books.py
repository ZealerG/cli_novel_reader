"""番茄小说搜索、章节、正文 API。

正文获取方案(已验证):reader 页面 SSR HTML 内嵌 __INITIAL_STATE__,
含完整正文(带 PUA 字体混淆),配合 fontMap 解密即可,无需 API 签名。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import os

import httpx

from cli_novel_reader.fanqie.client import FanqieClient

# fontMap 随项目分发(TRNovel 社区维护,共 362 条 PUA→汉字映射)
_DEFAULT_FONTMAP_PATH = Path(__file__).parent / "data" / "content_fontmap.json"

_WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


class BooksAPI:
    """封装番茄小说内容获取。

    搜索/目录走官方网页 API(目录无需签名),正文走 reader SSR HTML。
    """

    FANQIE_BASE = "https://fanqienovel.com"

    def __init__(self, client: FanqieClient, fontmap_path: Path | None = None) -> None:
        self._client = client
        self._fontmap_path = fontmap_path or _DEFAULT_FONTMAP_PATH
        self._fontmap: dict[str, str] = self._load_fontmap()

    # ── fontMap ────────────────────────────────────────

    def _load_fontmap(self) -> dict[str, str]:
        if self._fontmap_path.exists():
            try:
                data = json.loads(self._fontmap_path.read_text("utf-8"))
                return {k.upper(): v for k, v in data.items()}
            except Exception:
                pass
        return {}

    def decode_pua(self, text: str) -> str:
        """将 PUA 私用区字符按 fontMap 还原为正常汉字。"""
        if not self._fontmap:
            return text
        out = []
        for ch in text:
            code = f"{ord(ch):X}"
            out.append(self._fontmap.get(code, ch))
        return "".join(out)

    # ── 章节目录(无需签名) ────────────────────────────

    async def get_chapters(self, book_id: str) -> list[dict]:
        """获取书籍章节目录(官方目录接口,无需签名)。"""
        try:
            r = await self._client.get(
                "/api/reader/directory/detail",
                params={"bookId": book_id},
            )
            if r.get("code") != 0:
                return []
            data = r.get("data", {})
            vols = data.get("chapterListWithVolume", [])
            result: list[dict] = []
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
            # fallback: 用 allItemIds
            if not result:
                ids = data.get("allItemIds", [])
                result = [{"chapter_id": cid, "title": f"第{i+1}章", "order": str(i + 1)}
                          for i, cid in enumerate(ids)]
            return result
        except Exception:
            return []

    # ── 正文(unidbg 服务优先,SSR 兜底) ────────────────

    UNIDBG_BASE = os.environ.get("UNIDBG_BASE", "http://127.0.0.1:8099")

    async def get_content(self, chapter_id: str, book_id: str = "") -> dict | None:
        """获取章节正文。

        优先走 unidbg 服务(完整内容,需签名),失败则回退到
        reader 页 SSR HTML(仅前几章完整,后续只有试读片段)。
        返回 {title, paragraphs}。
        """
        # 1. 尝试 unidbg 服务(完整章节)
        if book_id:
            result = await self._get_content_unidbg(book_id, chapter_id)
            if result:
                return result
        # 2. 回退:SSR HTML + fontMap 解密
        return await self._get_content_ssr(chapter_id)

    async def _get_content_unidbg(self, book_id: str, chapter_id: str) -> dict | None:
        """通过 unidbg 服务获取完整章节内容(带 App 签名)。"""
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get(
                    f"{self.UNIDBG_BASE}/api/fqnovel/chapter/{book_id}/{chapter_id}"
                )
            data = r.json()
            if data.get("code") != 0:
                return None
            d = data.get("data", {})
            txt = d.get("txtContent", "")
            if not txt:
                return None
            paragraphs = [p.strip() for p in txt.splitlines() if p.strip()]
            return {
                "title": d.get("title", ""),
                "paragraphs": paragraphs,
            }
        except Exception:
            return None

    async def _get_content_ssr(self, chapter_id: str) -> dict | None:
        """通过 reader 页 SSR HTML 获取正文(兜底,仅前几章完整)。"""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
                r = await c.get(
                    f"{self.FANQIE_BASE}/reader/{chapter_id}",
                    headers={
                        "User-Agent": _WEB_UA,
                        "Referer": f"{self.FANQIE_BASE}/",
                        "Accept": "text/html",
                    },
                )
            html = r.text
            state = self._extract_initial_state(html)
            if not state:
                return None
            cd = state.get("reader", {}).get("chapterData", {})
            content = cd.get("content", "")
            title = cd.get("title", "")
            if not content:
                return None
            paragraphs = self._html_to_paragraphs(content)
            paragraphs = [self.decode_pua(p) for p in paragraphs]
            return {
                "title": title,
                "paragraphs": paragraphs,
            }
        except Exception:
            return None

    @staticmethod
    def _extract_initial_state(html: str) -> dict | None:
        """从 reader 页 HTML 提取 window.__INITIAL_STATE__ JSON。"""
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    @staticmethod
    def _html_to_paragraphs(content: str) -> list[str]:
        """从 chapterData.content 提取纯文本段落(去 HTML 标签、跳图片)。"""
        paragraphs = []
        for p in re.findall(r"<p[^>]*>(.*?)</p>", content, re.DOTALL):
            if "<img" in p:
                continue
            # 去 HTML 实体和标签
            text = re.sub(r"<[^>]+>", "", p).strip()
            if text:
                paragraphs.append(text)
        return paragraphs

    # ── 搜索(需签名,暂不支持) ────────────────────────

    async def search(self, keyword: str) -> list[dict]:
        """搜索小说。

        番茄网页搜索 API 需要 a_bogus 签名,匿名请求会被风控拦截返回空 body。
        暂不支持,建议在官方 App/网页搜索后用 book_id 直接加入书架。
        """
        return []
