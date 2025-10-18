"""Handler for the main click action."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import EconomyLog
from bot.keyboards.reply import kb_main_menu, kb_menu_only
from bot.services.economy import finish_order_reward
from bot.services.users import (
    add_xp_and_levelup,
    ensure_user,
    get_active_order,
    get_user_stats,
)
from bot.utils.time import utcnow

router = Router()


@router.message(F.text == RU.BTN_CLICK)
async def handle_click(message: Message) -> None:
    """Handle click action: progress active order or notify user."""

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            active_order = await get_active_order(session, user)
            if not active_order:
                await message.answer(RU.NO_ACTIVE_ORDER, reply_markup=kb_main_menu())
                return
            stats = await get_user_stats(session, user)
            click_power = stats["cp"]
            previous_progress = active_order.progress_clicks
            active_order.progress_clicks = min(
                active_order.required_clicks,
                active_order.progress_clicks + click_power,
            )
            if (
                (active_order.progress_clicks // 10) > (previous_progress // 10)
                or active_order.progress_clicks == active_order.required_clicks
            ):
                percentage = int(100 * active_order.progress_clicks / active_order.required_clicks)
                await message.answer(
                    RU.CLICK_PROGRESS.format(
                        cur=active_order.progress_clicks,
                        req=active_order.required_clicks,
                        pct=percentage,
                    )
                )
            if active_order.progress_clicks < active_order.required_clicks:
                return

            reward = finish_order_reward(active_order.required_clicks, stats["reward_mul_total"])
            xp_gain = int(round(active_order.required_clicks * 0.1))
            user.balance += reward
            await add_xp_and_levelup(user, xp_gain)
            active_order.finished = True
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="order_finish",
                    amount=reward,
                    meta={"order_id": active_order.order_id},
                    created_at=utcnow(),
                )
            )
            await message.answer(RU.ORDER_DONE.format(rub=reward, xp=xp_gain), reply_markup=kb_menu_only())
