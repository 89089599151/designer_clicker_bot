"""Handlers for managing inventory and equipment."""
from __future__ import annotations

from typing import List

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import Item, UserEquipment, UserItem
from bot.keyboards.reply import kb_confirm, kb_menu_only, kb_numeric_page
from bot.services.users import ensure_user
from bot.states import WardrobeState
from bot.utils.pagination import slice_page
from sqlalchemy import select

router = Router()


def _format_inventory(items: List[Item]) -> str:
    if not items:
        return "Инвентарь пуст."
    lines = [RU.WARDROBE_HEADER]
    lines.extend(f"[{index}] {item.name} ({item.slot}, T{item.tier})" for index, item in enumerate(items, 1))
    return "\n".join(lines)


async def _render_inventory(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            items = (
                await session.execute(
                    select(Item).join(UserItem, UserItem.item_id == Item.id).where(UserItem.user_id == user.id)
                )
            ).scalars().all()
            page = int((await state.get_data()).get("page", 0))
            sub, has_prev, has_next = slice_page(items, page)
            if not sub:
                await message.answer("Инвентарь пуст.", reply_markup=kb_menu_only())
                await state.update_data(inv_ids=[], page=page)
                return
            await message.answer(
                _format_inventory(sub),
                reply_markup=kb_numeric_page(range(1, len(sub) + 1), has_prev, has_next),
            )
            await state.update_data(inv_ids=[item.id for item in sub], page=page)


@router.message(F.text == RU.BTN_WARDROBE)
async def wardrobe_root(message: Message, state: FSMContext) -> None:
    await state.set_state(WardrobeState.browsing)
    await state.update_data(page=0)
    await _render_inventory(message, state)


@router.message(WardrobeState.browsing, F.text == RU.BTN_PREV)
async def wardrobe_prev(message: Message, state: FSMContext) -> None:
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_inventory(message, state)


@router.message(WardrobeState.browsing, F.text == RU.BTN_NEXT)
async def wardrobe_next(message: Message, state: FSMContext) -> None:
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_inventory(message, state)


@router.message(WardrobeState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
async def wardrobe_choose(message: Message, state: FSMContext) -> None:
    item_ids = (await state.get_data()).get("inv_ids", [])
    index = int(message.text) - 1
    if index < 0 or index >= len(item_ids):
        return
    item_id = item_ids[index]
    async with async_session_maker() as session:
        async with session.begin():
            item = await session.get(Item, item_id)
            await message.answer(f"Экипировать «{item.name}»?", reply_markup=kb_confirm(RU.BTN_EQUIP))
    await state.set_state(WardrobeState.equip_confirm)
    await state.update_data(item_id=item_id)


@router.message(WardrobeState.equip_confirm, F.text == RU.BTN_EQUIP)
async def wardrobe_equip(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    item_id = int(data["item_id"])
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            item = await session.get(Item, item_id)
            has_item = await session.scalar(
                select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item_id)
            )
            if not has_item:
                await message.answer(RU.EQUIP_NOITEM, reply_markup=kb_menu_only())
            else:
                equipment = await session.scalar(
                    select(UserEquipment).where(UserEquipment.user_id == user.id, UserEquipment.slot == item.slot)
                )
                if equipment:
                    equipment.item_id = item.id
                else:
                    session.add(UserEquipment(user_id=user.id, slot=item.slot, item_id=item.id))
                await message.answer(RU.EQUIP_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(WardrobeState.equip_confirm, F.text == RU.BTN_CANCEL)
async def wardrobe_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await wardrobe_root(message, state)
