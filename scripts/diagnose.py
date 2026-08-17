#!/usr/bin/env python3
"""番茄 API 联调诊断脚本。

用法:
  .venv/bin/python scripts/diagnose.py            # 网络通路 + 目录 + 正文
  .venv/bin/python scripts/diagnose.py --cookie "sessionid=xxx; ttwid=yyy; ..."
                                                  # 加上真实 Cookie 跑完整链路

检查项(带 ✓/✗):
  1. 网络可达 fanqienovel.com
  2. 章节目录(官方目录接口,无需签名)
  3. 正文获取(reader SSR HTML + fontMap 解密)
  4. Cookie 有效性(用户信息接口)
  5. 云端书架
  6. 云端进度拉取
  7. 进度上报回环(读→写→回读)
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_novel_reader.fanqie import BooksAPI, FanqieClient, ProgressSync


def ok(label: str) -> None:
    print(f"  \033[32m✓\033[0m {label}")


def fail(label: str, detail: str = "") -> None:
    print(f"  \033[31m✗\033[0m {label}" + (f"  ({detail})" if detail else ""))


def section(title: str) -> None:
    print(f"\n\033[1m── {title} ──\033[0m")


async def main() -> None:
    cookie = ""
    if "--cookie" in sys.argv:
        idx = sys.argv.index("--cookie")
        if idx + 1 < len(sys.argv):
            cookie = sys.argv[idx + 1]

    client = FanqieClient()
    sync = ProgressSync(client)
    books_api = BooksAPI(client)

    # ── 1. 网络可达 ──────────────────────────────────
    section("1. 网络通路")
    try:
        r = await client.get("/api/user/info/v2")
        ok(f"fanqienovel.com 可达 (HTTP code={r.get('code', '?')})")
    except Exception as e:
        fail("fanqienovel.com 不可达", str(e))
        return

    # 用一本已知 book_id 测试(TOMATO-Novel-Downloader 等常用测试 id)
    test_book_id = "7297316760233970688"

    # ── 2. 章节目录 ──────────────────────────────────
    section("2. 章节目录(官方目录接口)")
    try:
        chapters = await books_api.get_chapters(test_book_id)
        if chapters:
            ok(f"目录获取成功:共 {len(chapters)} 章")
            first_ch = chapters[0]
            print(f"     首章: {first_ch.get('title')} / id={first_ch.get('chapter_id')}")
            test_chapter_id = first_ch["chapter_id"]
        else:
            fail("目录返回 0 条")
            return
    except Exception as e:
        fail("目录获取失败", str(e))
        return

    # ── 3. 正文获取 ──────────────────────────────────
    section("3. 正文获取(reader SSR + fontMap 解密)")
    try:
        content = await books_api.get_content(test_chapter_id)
        if content and content.get("paragraphs"):
            ok(f"正文获取成功:{len(content['paragraphs'])} 段")
            print(f"     章节标题: {content['title']}")
            preview = content["paragraphs"][0][:60]
            print(f"     首段预览: {preview}...")
            # 检查是否还有未解密的 PUA
            pua_count = sum(1 for p in content["paragraphs"]
                           for ch in p if 0xE000 <= ord(ch) <= 0xF8FF)
            if pua_count == 0:
                ok("字体解密:无残留 PUA 字符")
            else:
                fail(f"字体解密:仍有 {pua_count} 个未解密 PUA", "fontMap 可能需更新")
        else:
            fail("正文获取失败", "返回空")
    except Exception as e:
        fail("正文获取失败", str(e))

    # ── 以下需要登录 ──────────────────────────────────
    if not cookie:
        section("4-7. 需登录(Cookie)")
        print("  \033[33m⏭ 跳过\033[0m  提供 Cookie 后可验证书架/进度同步")
        print('  用法: python scripts/diagnose.py --cookie "sessionid=...; ttwid=..."')
        print()
        print("  获取 Cookie 方法:")
        print("    1. 浏览器登录 https://fanqienovel.com")
        print("    2. F12 → Network → 刷新页面")
        print("    3. 点任意 /api 请求 → Request Headers → 复制 Cookie 值")
        await client.close()
        return

    client.save_cookie(cookie)

    # ── 4. Cookie 有效性 ─────────────────────────────
    section("4. Cookie 有效性")
    try:
        r = await client.get("/api/user/info/v2")
        if r.get("code") == 0:
            user = r.get("data", {})
            ok(f"登录有效:用户={user.get('name', user.get('user_name', '?'))}  id={user.get('id', '?')}")
        else:
            fail("Cookie 无效", r.get("message", str(r.get("code"))))
            await client.close()
            return
    except Exception as e:
        fail("用户信息请求失败", str(e))
        await client.close()
        return

    # ── 5. 云端书架 ──────────────────────────────────
    section("5. 云端书架")
    test_book_for_progress: str | None = None
    try:
        shelf = await sync.get_bookshelf()
        if shelf:
            ok(f"书架同步成功:{len(shelf)} 本书")
            for b in shelf[:5]:
                last = b.get("last_read_chapter", "")
                idx = b.get("read_chapter_idx", -1)
                print(f"     · {b.get('name')} [{b.get('status')}]  上次:{last} (idx={idx})")
            for b in shelf:
                if b.get("read_item_id") and b["read_item_id"] != "0":
                    test_book_for_progress = b["book_id"]
                    break
        else:
            fail("书架为空或获取失败")
    except Exception as e:
        fail("书架请求失败", str(e))

    # ── 6. 云端进度拉取 ──────────────────────────────
    section("6. 云端进度拉取")
    if test_book_for_progress:
        try:
            prog = await sync.fetch_progress(test_book_for_progress)
            if prog:
                ok(f"进度拉取成功:item_id={prog.get('item_id')} "
                   f"chapter_idx={prog.get('chapter_idx')} "
                   f"(第{prog.get('chapter_idx', -1) + 1}章)")
            else:
                fail("该书无云端进度记录")
        except Exception as e:
            fail("进度拉取失败", str(e))
    else:
        print("  \033[33m⏭ 跳过\033[0m  书架中没有带进度的书可测")

    # ── 7. 进度上报回环 ──────────────────────────────
    section("7. 进度上报回环(读→写→回读)")
    if test_book_for_progress:
        try:
            before = await sync.fetch_progress(test_book_for_progress)
            before_idx = before.get("chapter_idx", -1) if before else -1
            before_ts = before.get("read_timestamp", 0) if before else 0
            chapters = await books_api.get_chapters(test_book_for_progress)
            if chapters and before_idx >= 0 and before_idx < len(chapters):
                ch = chapters[before_idx]
                ok1 = await sync.report_progress(test_book_for_progress, ch["chapter_id"], before_idx)
                if ok1:
                    await asyncio.sleep(2)
                    after = await sync.fetch_progress(test_book_for_progress)
                    after_ts = after.get("read_timestamp", 0) if after else 0
                    if after_ts > before_ts:
                        ok(f"进度上报成功:timestamp {before_ts} → {after_ts}")
                        ok(f"回环验证通过:续读 第{before_idx+1}章 {ch.get('title', '')}")
                    else:
                        fail("回环验证失败", "timestamp 未更新")
                else:
                    fail("进度上报失败", "API 返回非 0")
            else:
                print("  \033[33m⏭ 跳过\033[0m  无法反查章节序号做回环")
        except Exception as e:
            fail("进度回环失败", str(e))
    else:
        print("  \033[33m⏭ 跳过\033[0m  需一本带进度的书")

    await client.close()
    print()


if __name__ == "__main__":
    asyncio.run(main())
