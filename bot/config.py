"""Configuration helpers for the Designer Clicker bot."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore


if load_dotenv:
    load_dotenv()


@dataclass(slots=True)
class Settings:
    """Environment driven settings for the bot runtime."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./designer.db")
    DAILY_BONUS_RUB: int = int(os.getenv("DAILY_BONUS_RUB", "100"))
    BASE_ADMIN_ID: int = int(os.getenv("BASE_ADMIN_ID", "0"))
    CLICK_RATE_BASE: int = int(os.getenv("CLICK_RATE_BASE", "10"))
    CLICK_RATE_MAX: int = int(os.getenv("CLICK_RATE_MAX", "15"))


SETTINGS = Settings()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application wide logging."""

    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


LOGGER = logging.getLogger("designer_clicker_bot")
