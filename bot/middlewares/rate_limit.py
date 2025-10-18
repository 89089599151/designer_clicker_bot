"""Rate limiting middleware for spam protection."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Awaitable, Callable, Deque, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import SETTINGS
from bot.constants import RU
from bot.database.base import async_session_maker
from bot.services.users import get_user_by_tg_id, get_user_click_limit

HandlerType = Callable[[Message, Dict], Awaitable[object]]


class RateLimiter:
    """Simple per-user rate limiter using in-memory deque."""

    def __init__(self, max_events: int = 100) -> None:
        self._events: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=max_events))

    def allow(self, user_id: int, limit_per_sec: int, now: Optional[float] = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        events = self._events[user_id]
        while events and timestamp - events[0] > 1.0:
            events.popleft()
        if len(events) >= limit_per_sec:
            return False
        events.append(timestamp)
        return True


class RateLimitMiddleware(BaseMiddleware):
    """Prevent spamming the click button beyond configured limits."""

    def __init__(self, limiter: Optional[RateLimiter] = None) -> None:
        super().__init__()
        self.limiter = limiter or RateLimiter()

    async def __call__(self, handler: HandlerType, event: Message, data: Dict) -> Optional[object]:
        if isinstance(event, Message) and (event.text or "") == RU.BTN_CLICK:
            tg_id = event.from_user.id
            async with async_session_maker() as session:
                user = await get_user_by_tg_id(session, tg_id)
                if user:
                    limit = await get_user_click_limit(
                        session,
                        user,
                        SETTINGS.CLICK_RATE_BASE,
                        SETTINGS.CLICK_RATE_MAX,
                    )
                else:
                    limit = SETTINGS.CLICK_RATE_BASE
            if not self.limiter.allow(tg_id, limit):
                await event.answer(RU.TOO_FAST)
                return None
        return await handler(event, data)
