"""Handlers for browsing and taking orders."""
from __future__ import annotations

from typing import List

from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import Order, UserOrder
from bot.keyboards.reply import kb_confirm, kb_numeric_page, kb_menu_only
from bot.services.economy import snapshot_required_clicks
from bot.services.users import (
    ensure_no_active_order,
    ensure_user,
    get_user_stats,
)
from bot.states import OrdersState
from bot.utils.pagination import slice_page
from bot.utils.time import utcnow
from sqlalchemy import select

router = Router()


def _format_orders(orders: List[Order]) -> str:
    lines = [RU.ORDERS_HEADER, ""]
    lines.extend(f"[{index}] {order.title} — мин. ур. {order.min_level}" for index, order in enumerate(orders, 1))
    return "\n".join(lines)


async def _render_orders_page(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            all_orders = (
                await session.execute(select(Order).where(Order.min_level <= user.level))
            ).scalars().all()
            page = int((await state.get_data()).get("page", 0))
            sub, has_prev, has_next = slice_page(all_orders, page)
            if not sub:
                await message.answer("Нет доступных заказов.", reply_markup=kb_menu_only())
                await state.update_data(order_ids=[], page=page)
                return
            await message.answer(
                _format_orders(sub),
                reply_markup=kb_numeric_page(range(1, len(sub) + 1), has_prev, has_next),
            )
            await state.update_data(order_ids=[order.id for order in sub], page=page)


@router.message(F.text == RU.BTN_ORDERS)
async def orders_root(message: Message, state: FSMContext) -> None:
    await state.set_state(OrdersState.browsing)
    await state.update_data(page=0)
    await _render_orders_page(message, state)


@router.message(OrdersState.browsing, F.text == RU.BTN_PREV)
async def orders_prev(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    page = max(0, int(data.get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_orders_page(message, state)


@router.message(OrdersState.browsing, F.text == RU.BTN_NEXT)
async def orders_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    page = int(data.get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_orders_page(message, state)


@router.message(OrdersState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
async def orders_choose(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_ids = data.get("order_ids", [])
    index = int(message.text) - 1
    if index < 0 or index >= len(order_ids):
        return
    order_id = order_ids[index]

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            if not await ensure_no_active_order(session, user):
                await message.answer(RU.ORDER_ALREADY, reply_markup=kb_menu_only())
                await state.clear()
                return
            order = await session.get(Order, order_id)
            stats = await get_user_stats(session, user)
            required = snapshot_required_clicks(order.base_clicks, user.level, stats["req_clicks_pct"])
            await state.update_data(order_id=order_id, required_clicks=required)
            await state.set_state(OrdersState.confirm)
            await message.answer(
                f"Взять заказ «{order.title}»?\nТребуемые клики: {required}",
                reply_markup=kb_confirm(RU.BTN_TAKE),
            )


@router.message(OrdersState.confirm, F.text == RU.BTN_TAKE)
async def take_order(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = int(data["order_id"])
    required_clicks = int(data["required_clicks"])

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            if not await ensure_no_active_order(session, user):
                await message.answer(RU.ORDER_ALREADY, reply_markup=kb_menu_only())
                await state.clear()
                return
            stats = await get_user_stats(session, user)
            session.add(
                UserOrder(
                    user_id=user.id,
                    order_id=order_id,
                    progress_clicks=0,
                    required_clicks=required_clicks,
                    started_at=utcnow(),
                    finished=False,
                    canceled=False,
                    reward_snapshot_mul=stats["reward_mul_total"],
                )
            )
            order = await session.get(Order, order_id)
            await message.answer(RU.ORDER_TAKEN.format(title=order.title), reply_markup=kb_menu_only())
    await state.clear()


@router.message(OrdersState.confirm, F.text == RU.BTN_CANCEL)
async def orders_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await orders_root(message, state)
