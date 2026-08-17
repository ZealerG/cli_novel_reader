"""应用配置:路径、默认主题、同步开关。"""
from __future__ import annotations

import os
from pathlib import Path

# 数据目录(进度缓存、Cookie、书源配置)
DATA_DIR = Path(os.environ.get("CLI_NOVEL_DATA", Path.home() / ".cli-novel-reader"))
COOKIE_FILE = DATA_DIR / "cookie.txt"
CONFIG_FILE = DATA_DIR / "config.json"

# 默认伪装主题
DEFAULT_DISGUISE = os.environ.get("CLI_NOVEL_DISGUISE", "vim")

# 进度同步间隔(秒)
SYNC_INTERVAL = float(os.environ.get("CLI_NOVEL_SYNC_INTERVAL", "30"))
