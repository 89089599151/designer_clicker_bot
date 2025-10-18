"""Handlers for managing the hireable team."""
from __future__ import annotations

from typing import Dict, List

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.database.models import EconomyLog, TeamMember, UserTeam
from bot.keyboards.reply import kb_confirm, kb_menu_only, kb_numeric_page
from bot.services.economy import team_income_per_min
from bot.services.users import ensure_user
from bot.states import TeamState
from bot.utils.pagination import slice_page
from bot.utils.time import utcnow
from sqlalchemy import select

router = Router()


def _format_team(members: List[TeamMember], levels: Dict[int, int], costs: Dict[int, int]) -> str:
    lines = [RU.TEAM_HEADER]
    for index, member in enumerate(members, 1):
        level = levels.get(member.id, 0)
        income = team_income_per_min(member.base_income_per_min, max(1, level)) if level > 0 else 0.0
        lines.append(
            f"[{index}] {member.name}: {income:.0f}/мин, ур. {level}, цена повышения {costs[member.id]} {RU.CURRENCY}"
        )
    return "\n".join(lines)


async def _render_team(message: Message, state: FSMContext) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            members = (await session.execute(select(TeamMember))).scalars().all()
            level_rows = (
                await session.execute(
                    select(UserTeam.member_id, UserTeam.level).where(UserTeam.user_id == user.id)
                )
            ).all()
            levels = {member_id: level for member_id, level in level_rows}
            costs = {
                member.id: int(round(member.base_cost * (1.22 ** max(0, levels.get(member.id, 0)))))
                for member in members
            }
            page = int((await state.get_data()).get("page", 0))
            sub, has_prev, has_next = slice_page(members, page)
            if not sub:
                await message.answer("Команда недоступна.", reply_markup=kb_menu_only())
                await state.update_data(member_ids=[], page=page)
                return
            await message.answer(
                _format_team(sub, levels, costs),
                reply_markup=kb_numeric_page(range(1, len(sub) + 1), has_prev, has_next),
            )
            await state.update_data(member_ids=[member.id for member in sub], page=page)


@router.message(F.text == RU.BTN_TEAM)
async def team_root(message: Message, state: FSMContext) -> None:
    await state.set_state(TeamState.browsing)
    await state.update_data(page=0)
    await _render_team(message, state)


@router.message(TeamState.browsing, F.text == RU.BTN_PREV)
async def team_prev(message: Message, state: FSMContext) -> None:
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_team(message, state)


@router.message(TeamState.browsing, F.text == RU.BTN_NEXT)
async def team_next(message: Message, state: FSMContext) -> None:
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_team(message, state)


@router.message(TeamState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
async def team_choose(message: Message, state: FSMContext) -> None:
    member_ids = (await state.get_data()).get("member_ids", [])
    index = int(message.text) - 1
    if index < 0 or index >= len(member_ids):
        return
    member_id = member_ids[index]
    async with async_session_maker() as session:
        async with session.begin():
            member = await session.get(TeamMember, member_id)
            await message.answer(f"Повысить «{member.name}»?", reply_markup=kb_confirm(RU.BTN_UPGRADE))
    await state.set_state(TeamState.confirm)
    await state.update_data(member_id=member_id)


@router.message(TeamState.confirm, F.text == RU.BTN_UPGRADE)
async def team_upgrade(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    member_id = int(data["member_id"])
    async with async_session_maker() as session:
        async with session.begin():
            user = await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
            member = await session.get(TeamMember, member_id)
            user_team = await session.scalar(
                select(UserTeam).where(UserTeam.user_id == user.id, UserTeam.member_id == member_id)
            )
            level = user_team.level if user_team else 0
            cost = int(round(member.base_cost * (1.22 ** level)))
            if user.balance < cost:
                await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
            else:
                user.balance -= cost
                if user_team:
                    user_team.level += 1
                else:
                    session.add(UserTeam(user_id=user.id, member_id=member_id, level=1))
                session.add(
                    EconomyLog(
                        user_id=user.id,
                        type="team_upgrade",
                        amount=-cost,
                        meta={"member": member.code, "lvl": level + 1},
                        created_at=utcnow(),
                    )
                )
                await message.answer(RU.UPGRADE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(TeamState.confirm, F.text == RU.BTN_CANCEL)
async def team_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await team_root(message, state)
