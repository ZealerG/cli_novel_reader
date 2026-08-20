"""共享"工作噪声"素材:git / diff / pytest / HTTP / 容器日志。

伪装主题在小说段落之间穿插这些看似真实的工作输出,
让屏幕保持"有人在干活"的观感;小说行保持暗色,成为视觉噪声
的一部分,一眼扫过去不会成为焦点。
"""
from __future__ import annotations

import datetime as _dt
import random


class Filler:
    """确定性伪随机噪声生成器(同一章节内序列稳定)。"""

    GIT_FILES = [
        "src/utils/rate_limit.py",
        "src/api/handlers.py",
        "src/cache/memory_store.py",
        "src/parser/xml_reader.py",
        "tests/test_worker.py",
        "config/settings.yaml",
        "scripts/migrate_db.py",
        "docs/design-notes.md",
    ]

    def __init__(self, seed, *, start: _dt.datetime | None = None) -> None:
        self._rng = random.Random(seed)
        self._now = start or _dt.datetime.now()
        self._i = 0

    # ── 基础工具 ───────────────────────────────────────

    def choice(self, pool) -> object:
        return self._rng.choice(pool)

    def chance(self, p: float) -> bool:
        return self._rng.random() < p

    def _advance(self) -> None:
        self._i += 1
        self._now += _dt.timedelta(seconds=self._rng.randint(2, 9) / 10.0)

    def clock(self, fmt: str = "%H:%M:%S") -> str:
        self._advance()
        return self._now.strftime(fmt)

    def iso_ts(self) -> str:
        self._advance()
        return self._now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{self._rng.randint(100, 999):03d}Z"

    def git_hash(self) -> str:
        return "%07x" % self._rng.getrandbits(28)

    def number(self, lo: int, hi: int) -> int:
        return self._rng.randint(lo, hi)

    # ── 各类工作输出 ───────────────────────────────────

    def git_line(self) -> str:
        kind = self.choice(["M", "M", "A", "??"])
        fname = self.choice(self.GIT_FILES)
        if kind == "??":
            return f"?? {fname}.bak"
        if kind == "A":
            return f"{kind}  {fname}"
        return f"{kind}  {fname}   +{self.number(1, 42)}, -{self.number(0, 9)}"

    def pytest_line(self) -> str:
        tpl = self.choice([
            f"tests/test_worker.py::test_{self.word()}{self.word()} PASSED",
            f"tests/test_parser.py::test_{self.word()} PASSED [ {self.number(40, 99)}%]",
            f"tests/test_handlers.py::test_{self.word()} SKIPPED (no db)",
        ])
        return tpl

    def http_line(self) -> str:
        code = self.choice([200, 200, 200, 201, 204, 304, 400, 404, 500])
        ms = self.number(2, 480)
        route = self.choice([
            "/api/books/search?kw=main",
            "/api/books/detail?id=7fa1c2",
            "/api/reader/chapter/1015",
            "/api/shelf/list?page=2",
            "/health",
        ])
        return f"{self.clock()} GET {route} → {code} {ms}.{self.number(0, 9)}ms"

    def worker_line(self) -> str:
        """结构化服务日志(如 queue worker / k8s pod)。"""
        level = self.choice(["INFO", "INFO", "INFO", "WARN", "DEBUG"])
        mid = self.choice(["queue.worker", "story.engine", "api.gateway", "cache.sync"])
        metric = self.choice([
            f"task=parse-{self.git_hash()[:6]}",
            f"shard={self.number(0, 15)} processed={self.number(52, 9999)}",
            f"latency_ms={self.number(1, 240)} segments={self.number(4, 120)}",
            f"evicted={self.number(0, 32)} hit_rate=0.{self.number(61, 99)}",
            f"queue_depth={self.number(0, 87)} retry={self.number(0, 3)}",
        ])
        return f"{self.iso_ts()}  {level:<5} {mid}  {metric}"

    def build_line(self) -> str:
        tpl = self.choice([
            f"modules transformed   {self.number(42, 1442)} modules.",
            f"dist/static/css/app.css  {self.number(34, 512)} kB │ gzip {self.number(4, 88)} kB",
            f"✓ {self.number(31, 2145)} files, {self.number(8, 340)} chunks (0 missing)",
            f"[warn] chunk size exceeds limit ({self.number(512, 1024)} kB) → code split",
        ])
        return tpl

    # ── 真实风格工作输出(genact 式) ───────────────────

    def docker_line(self) -> str:
        """仿 docker build 输出。"""
        step = self.number(1, 12)
        tpl = self.choice([
            f"Step {step}/12 : FROM node:21-alpine AS builder",
            f" ---> {self.git_hash()}",
            f"Step {step}/12 : RUN npm ci --production",
            f" ---> Running in {self.git_hash()[:8]}",
            f" ---> {self.git_hash()}",
            f"Removing intermediate container {self.git_hash()[:8]}",
            f"Successfully built {self.git_hash()}",
            f"Successfully tagged story-engine:{self.choice(['latest', 'v1.2.3', 'dev'])}",
        ])
        return tpl

    def cargo_line(self) -> str:
        """仿 cargo build 输出。"""
        crate = self.choice(["story_engine", "api_client", "text_parser", "rate_limit"])
        tpl = self.choice([
            f"   Compiling {crate} v0.{self.number(1, 8)}.{self.number(0, 19)}",
            f"    Finished release [optimized] target(s) in {self.number(3, 47)}.{self.number(0, 9)}s",
            f"     Running `target/release/{crate}`",
            f"warning: unused variable: `config`",
            f"  --> src/main.rs:{self.number(10, 320)}:{self.number(1, 40)}",
        ])
        return tpl

    def npm_line(self) -> str:
        """仿 npm install 输出。"""
        pkg = self.choice([
            "express", "lodash", "axios", "chalk", "dotenv",
            "textual", "rich", "httpx", "pydantic",
        ])
        tpl = self.choice([
            f"added {self.number(12, 348)} packages in {self.number(2, 18)}s",
            f"{pkg}@{self.number(1, 18)}.{self.number(0, 99)}.{self.number(0, 99)}",
            f"│ {pkg} │ gzip: {self.number(4, 124)} kB",
            f"npm warn deprecated {pkg}@{self.number(1, 5)}.0.0: Use newer version",
        ])
        return tpl

    def diff_hunk(self, line_no: int | None = None) -> list[str]:
        """生成一个绿/红的小 diff 块。"""
        start = line_no or self.number(12, 320)
        fname = self.choice(self.GIT_FILES)
        return [
            f"@@ -{start},7 +{start},7 @@ {fname}",
            f"     def fetch(url, timeout={self.number(3, 30)}):",
            f"-        return client.get(url)",
            f"+        return client.get(url, timeout=timeout)",
            f" ",
            f"-    queue.push(job, priority=0)",
            f"+    queue.push(job, priority=3, retries=2)",
        ]

    def think_line(self) -> str:
        return self.choice([
            "分析现有实现,确认无破坏性改动…",
            "检查边界条件:空输入、超时、重试…",
            "对比两处实现,合并公共路径…",
            "读 tests 确认预期行为没有变化…",
            "输出改动 diff,等待确认…",
        ])

    def code_line(self) -> str:
        """生成一行随机代码(仿 Python)。"""
        kind = self.choice(["import", "assign", "call", "def", "if", "for", "return", "comment"])
        if kind == "import":
            pkg = self.choice(["json", "logging", "pathlib", "typing", "asyncio", "hashlib", "collections"])
            return f"import {pkg}"
        elif kind == "assign":
            var = self.choice(["result", "data", "config", "ctx", "cache", "payload"])
            val = self.choice([
                f"self._decode({self.word()})",
                f"json.loads(body)",
                f"{{'id': {self.number(1, 9999)}, 'ts': time.time()}}",
                f"[x for x in items if x.ok]",
                f"None",
            ])
            indent = self.choice(["", "    ", "        "])
            return f"{indent}{var} = {val}"
        elif kind == "call":
            fn = self.choice(["log.debug", "cache.set", "queue.push", "parser.parse", "client.get"])
            arg = self.choice([
                f"'seg_{self.word()}'",
                f"key, value, ttl={self.number(30, 3600)}",
                f"raw, retries={self.number(0, 3)}",
                f"url, timeout={self.number(3, 30)}",
            ])
            indent = self.choice(["    ", "        "])
            return f"{indent}{fn}({arg})"
        elif kind == "def":
            name = self.choice(["parse", "_normalize", "_decode", "_validate", "_flush", "_retry"])
            indent = self.choice(["", "    "])
            return f"{indent}def {name}(self, raw: str) -> dict:"
        elif kind == "if":
            cond = self.choice([
                "not raw",
                "resp.status != 200",
                "cache.is_expired(key)",
                "retry < MAX_RETRIES",
                "not result",
            ])
            indent = self.choice(["    ", "        "])
            return f"{indent}if {cond}:"
        elif kind == "for":
            loop = self.choice([
                "for item in items:",
                "for key, val in data.items():",
                "for _ in range(retries):",
            ])
            indent = self.choice(["    ", "        "])
            return f"{indent}{loop}"
        elif kind == "return":
            ret = self.choice(["None", "result", "self._cache.get(key)", "parsed"])
            indent = self.choice(["    ", "        "])
            return f"{indent}return {ret}"
        else:
            comment = self.choice([
                "# TODO: refactor this",
                "# FIXME: handle edge case",
                "# NOTE: see issue #429",
                "# type: ignore[misc]",
            ])
            indent = self.choice(["", "    ", "        "])
            return f"{indent}{comment}"

    def word(self) -> str:
        return "%05x" % self._rng.getrandbits(20)