"""Handlers for the in-game shop."""
from __future__ import annotations

from typing import List

from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import Boost, EconomyLog, Item, UserBoost, UserItem
from bot.keyboards.reply import kb_confirm, kb_menu_only, kb_numeric_page, kb_shop_menu
from bot.services.economy import upgrade_cost
from bot.services.users import ensure_user
from bot.states import ShopState
from bot.utils.pagination import slice_page
from bot.utils.time import utcnow
from sqlalchemy import select

router = Router()


def _format_boosts(boosts: List[Boost], levels: dict[int, int]) -> List[str]:
    lines: List[str] = []
    for index, boost in enumerate(boosts, 1):
        current_level = levels.get(boost.id, 0)
        next_level = current_level + 1
        cost = upgrade_cost(boost.base_cost, boost.growth, next_level)
        lines.append(f"[{index}] {boost.name} — ур. след. {next_level}, {cost} {RU.CURRENCY}")
    return lines


def _format_items(items: List[Item]) -> List[str]:
    lines: List[str] = []
    for index, item in enumerate(items, 1):
        lines.append(f"[{index}] {item.name} ({item.slot}, T{item.tier}) — {item.price} {RU.CURRENCY}")
    return lines


@router.message(F.text == RU.BTN_SHOP)
async def shop_root(message: Message, state: FSMContext) -> None:
    await state.set_state(ShopState.root)
    await message.answer(RU.SHOP_HEADER, reply_markup=kb_shop_menu())


async def _render_boosts(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            boosts = (await session.execute(select(Boost))).scalars().all()
            levels = {
                boost_id: level
                for boost_id, level in (
                    await session.execute(
                        select(UserBoost.boost_id, UserBoost.level).where(UserBoost.user_id == user.id)
                    )
                ).all()
            }
            page = int((await state.get_data()).get("page", 0))
            sub, has_prev, has_next = slice_page(boosts, page)
            if not sub:
                await message.answer("Нет бустов.", reply_markup=kb_menu_only())
                await state.update_data(boost_ids=[], page=page)
                return
            lines = _format_boosts(sub, levels)
            await message.answer("\n".join(lines), reply_markup=kb_numeric_page(range(1, len(sub) + 1), has_prev, has_next))
            await state.update_data(boost_ids=[boost.id for boost in sub], page=page)


@router.message(ShopState.root, F.text == RU.BTN_BOOSTS)
async def shop_boosts(message: Message, state: FSMContext) -> None:
    await state.set_state(ShopState.boosts)
    await state.update_data(page=0)
    await _render_boosts(message, state)


@router.message(ShopState.boosts, F.text.in_({"1", "2", "3", "4", "5"}))
async def shop_choose_boost(message: Message, state: FSMContext) -> None:
    ids = (await state.get_data()).get("boost_ids", [])
    index = int(message.text) - 1
    if index < 0 or index >= len(ids):
        return
    boost_id = ids[index]
    async with async_session_maker() as session:
        async with session.begin():
            boost = await session.get(Boost, boost_id)
            await message.answer(
                f"Купить буст «{boost.name}»?",
                reply_markup=kb_confirm(RU.BTN_BUY),
            )
    await state.set_state(ShopState.confirm_boost)
    await state.update_data(boost_id=boost_id)


@router.message(ShopState.boosts, F.text == RU.BTN_PREV)
async def shop_boosts_prev(message: Message, state: FSMContext) -> None:
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_boosts(message, state)


@router.message(ShopState.boosts, F.text == RU.BTN_NEXT)
async def shop_boosts_next(message: Message, state: FSMContext) -> None:
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_boosts(message, state)


@router.message(ShopState.confirm_boost, F.text == RU.BTN_BUY)
async def shop_buy_boost(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    boost_id = int(data["boost_id"])

    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            boost = await session.get(Boost, boost_id)
            user_boost = await session.scalar(
                select(UserBoost).where(UserBoost.user_id == user.id, UserBoost.boost_id == boost_id)
            )
            current_level = user_boost.level if user_boost else 0
            next_level = current_level + 1
            cost = upgrade_cost(boost.base_cost, boost.growth, next_level)
            if user.balance < cost:
                await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
            else:
                user.balance -= cost
                if user_boost:
                    user_boost.level = next_level
                else:
                    session.add(UserBoost(user_id=user.id, boost_id=boost_id, level=1))
                session.add(
                    EconomyLog(
                        user_id=user.id,
                        type="buy_boost",
                        amount=-cost,
                        meta={"boost": boost.code, "lvl": next_level},
                        created_at=utcnow(),
                    )
                )
                await message.answer(RU.PURCHASE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(ShopState.confirm_boost, F.text == RU.BTN_CANCEL)
async def shop_cancel_boost(message: Message, state: FSMContext) -> None:
    await state.clear()
    await shop_boosts(message, state)


async def _render_items(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            items = (
                await session.execute(select(Item).where(Item.min_level <= user.level))
            ).scalars().all()
            page = int((await state.get_data()).get("page", 0))
            sub, has_prev, has_next = slice_page(items, page)
            if not sub:
                await message.answer("Нет доступных предметов.", reply_markup=kb_menu_only())
                await state.update_data(item_ids=[], page=page)
                return
            lines = _format_items(sub)
            await message.answer(
                "\n".join(lines),
                reply_markup=kb_numeric_page(range(1, len(sub) + 1), has_prev, has_next),
            )
            await state.update_data(item_ids=[item.id for item in sub], page=page)


@router.message(ShopState.root, F.text == RU.BTN_EQUIPMENT)
async def shop_equipment(message: Message, state: FSMContext) -> None:
    await state.set_state(ShopState.equipment)
    await state.update_data(page=0)
    await _render_items(message, state)


@router.message(ShopState.equipment, F.text.in_({"1", "2", "3", "4", "5"}))
async def shop_choose_item(message: Message, state: FSMContext) -> None:
    item_ids = (await state.get_data()).get("item_ids", [])
    index = int(message.text) - 1
    if index < 0 or index >= len(item_ids):
        return
    item_id = item_ids[index]
    async with async_session_maker() as session:
        async with session.begin():
            item = await session.get(Item, item_id)
            await message.answer(
                f"Купить предмет «{item.name}» за {item.price} {RU.CURRENCY}?",
                reply_markup=kb_confirm(RU.BTN_BUY),
            )
    await state.set_state(ShopState.confirm_item)
    await state.update_data(item_id=item_id)


@router.message(ShopState.equipment, F.text == RU.BTN_PREV)
async def shop_items_prev(message: Message, state: FSMContext) -> None:
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_items(message, state)


@router.message(ShopState.equipment, F.text == RU.BTN_NEXT)
async def shop_items_next(message: Message, state: FSMContext) -> None:
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_items(message, state)


@router.message(ShopState.confirm_item, F.text == RU.BTN_BUY)
async def shop_buy_item(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    item_id = int(data["item_id"])
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            item = await session.get(Item, item_id)
            has_item = await session.scalar(
                select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item_id)
            )
            if has_item:
                await message.answer("Уже куплено.", reply_markup=kb_menu_only())
            elif user.balance < item.price:
                await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
            else:
                user.balance -= item.price
                session.add(UserItem(user_id=user.id, item_id=item_id))
                session.add(
                    EconomyLog(
                        user_id=user.id,
                        type="buy_item",
                        amount=-item.price,
                        meta={"item": item.code},
                        created_at=utcnow(),
                    )
                )
                await message.answer(RU.PURCHASE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(ShopState.confirm_item, F.text == RU.BTN_CANCEL)
async def shop_cancel_item(message: Message, state: FSMContext) -> None:
    await state.clear()
    await shop_equipment(message, state)
