"""Profile, daily bonus and order management handlers."""
from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.types import Message
from bot.config import SETTINGS
from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import EconomyLog, Order
from bot.keyboards.reply import kb_main_menu, kb_profile_menu
from bot.services.economy import xp_to_level
from bot.services.users import (
    calc_passive_income_rate,
    ensure_user,
    get_active_order,
    get_user_stats,
)
from bot.utils.time import utcnow

router = Router()


@router.message(F.text == RU.BTN_PROFILE)
async def profile_show(message: Message) -> None:
    """Show player profile and stats."""

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            stats = await get_user_stats(session, user)
            rate = await calc_passive_income_rate(session, user, stats["passive_mul_total"])
            active = await get_active_order(session, user)
            order_text = "нет"
            if active:
                order_row = await session.get(Order, active.order_id)
                order_text = f"{order_row.title}: {active.progress_clicks}/{active.required_clicks}"
            xp_required = xp_to_level(user.level)
            text = RU.PROFILE.format(
                lvl=user.level,
                xp=user.xp,
                xp_need=xp_required,
                rub=user.balance,
                cp=stats["cp"],
                pm=int(rate * 60),
                order=order_text,
            )
            await message.answer(text, reply_markup=kb_profile_menu(has_active_order=bool(active)))


@router.message(F.text == RU.BTN_DAILY)
async def profile_daily(message: Message) -> None:
    """Grant daily bonus if available."""

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            now = utcnow()
            if user.daily_bonus_at and (now - user.daily_bonus_at) < timedelta(hours=24):
                await message.answer(RU.DAILY_WAIT, reply_markup=kb_main_menu())
                return
            user.daily_bonus_at = now
            user.balance += SETTINGS.DAILY_BONUS_RUB
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="daily_bonus",
                    amount=SETTINGS.DAILY_BONUS_RUB,
                    meta=None,
                    created_at=now,
                )
            )
            await message.answer(RU.DAILY_OK.format(rub=SETTINGS.DAILY_BONUS_RUB), reply_markup=kb_main_menu())


@router.message(F.text == RU.BTN_CANCEL_ORDER)
async def profile_cancel_order(message: Message, state: FSMContext) -> None:
    """Cancel active order if present."""

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            active = await get_active_order(session, user)
            if not active:
                await message.answer("Нет активного заказа.", reply_markup=kb_main_menu())
                return
            active.canceled = True
            await message.answer(RU.ORDER_CANCELED, reply_markup=kb_main_menu())
