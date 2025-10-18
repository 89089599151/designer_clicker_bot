"""User centric service helpers."""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import EQUIPMENT_SLOTS
from bot.database.models import (
    Boost,
    EconomyLog,
    Item,
    TeamMember,
    User,
    UserBoost,
    UserEquipment,
    UserOrder,
    UserTeam,
)
from bot.database.seed import seed_if_needed
from bot.services.economy import team_income_per_min, xp_to_level
from bot.utils.time import utcnow


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    """Return user by Telegram identifier."""

    return await session.scalar(select(User).where(User.tg_id == tg_id))


async def ensure_user(session: AsyncSession, tg_id: int, first_name: str) -> User:
    """Fetch or create a ``User`` entry."""

    await seed_if_needed(session)
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        await apply_offline_income(session, user)
        return user

    now = utcnow()
    user = User(
        tg_id=tg_id,
        first_name=first_name or "",
        balance=200,
        cp_base=1,
        reward_mul=0.0,
        passive_mul=0.0,
        level=1,
        xp=0,
        last_seen=now,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()
    for slot in EQUIPMENT_SLOTS:
        session.add(UserEquipment(user_id=user.id, slot=slot, item_id=None))
    return user


async def get_active_order(session: AsyncSession, user: User) -> Optional[UserOrder]:
    """Return active order for user if any."""

    stmt = select(UserOrder).where(
        UserOrder.user_id == user.id,
        UserOrder.finished.is_(False),
        UserOrder.canceled.is_(False),
    )
    return await session.scalar(stmt)


async def ensure_no_active_order(session: AsyncSession, user: User) -> bool:
    """Ensure user has no active order."""

    return await get_active_order(session, user) is None


async def add_xp_and_levelup(user: User, xp_gain: int) -> None:
    """Increase XP and level up if thresholds exceeded."""

    user.xp += xp_gain
    level = user.level
    while user.xp >= xp_to_level(level):
        user.xp -= xp_to_level(level)
        level += 1
    user.level = level


async def get_user_stats(session: AsyncSession, user: User) -> Dict[str, float]:
    """Return aggregate stats based on boosts and equipment."""

    boost_rows = (
        await session.execute(
            select(Boost.type, UserBoost.level, Boost.step_value)
            .join(Boost, Boost.id == UserBoost.boost_id)
            .where(UserBoost.user_id == user.id)
        )
    ).all()
    cp_add = 0
    reward_add = 0.0
    passive_add = 0.0
    for boost_type, level, step_value in boost_rows:
        if boost_type == "cp":
            cp_add += int(level * step_value)
        elif boost_type == "reward":
            reward_add += level * step_value
        elif boost_type == "passive":
            passive_add += level * step_value

    items = (
        await session.execute(
            select(Item.bonus_type, Item.bonus_value)
            .join(UserEquipment, UserEquipment.item_id == Item.id)
            .where(UserEquipment.user_id == user.id)
        )
    ).all()
    cp_pct = 0.0
    passive_pct = 0.0
    req_clicks_pct = 0.0
    reward_pct = 0.0
    ratelimit_plus = 0.0
    for bonus_type, value in items:
        if bonus_type == "cp_pct":
            cp_pct += value
        elif bonus_type == "passive_pct":
            passive_pct += value
        elif bonus_type == "req_clicks_pct":
            req_clicks_pct += value
        elif bonus_type == "reward_pct":
            reward_pct += value
        elif bonus_type == "ratelimit_plus":
            ratelimit_plus += value

    cp = int(round((user.cp_base + cp_add) * (1 + cp_pct)))
    reward_mul_total = 1.0 + user.reward_mul + reward_add + reward_pct
    passive_mul_total = 1.0 + user.passive_mul + passive_add + passive_pct
    return {
        "cp": max(1, cp),
        "reward_mul_total": max(0.0, reward_mul_total),
        "passive_mul_total": max(0.0, passive_mul_total),
        "req_clicks_pct": max(0.0, req_clicks_pct),
        "ratelimit_plus": ratelimit_plus,
    }


async def calc_passive_income_rate(session: AsyncSession, user: User, passive_multiplier: float) -> float:
    """Calculate passive income per second."""

    rows = (
        await session.execute(
            select(TeamMember.base_income_per_min, UserTeam.level)
            .join(UserTeam, TeamMember.id == UserTeam.member_id)
            .where(UserTeam.user_id == user.id)
        )
    ).all()
    income_per_minute = sum(team_income_per_min(base, level) for base, level in rows)
    return (income_per_minute / 60.0) * passive_multiplier


async def apply_offline_income(session: AsyncSession, user: User) -> int:
    """Apply passive income for time spent offline."""

    now = utcnow()
    delta = max(0.0, (now - user.last_seen).total_seconds())
    user.last_seen = now
    stats = await get_user_stats(session, user)
    rate = await calc_passive_income_rate(session, user, stats["passive_mul_total"])
    amount = int(rate * delta)
    if amount > 0:
        user.balance += amount
        session.add(
            EconomyLog(
                user_id=user.id,
                type="passive",
                amount=amount,
                meta={"sec": int(delta)},
                created_at=now,
            )
        )
    return amount


async def get_user_click_limit(session: AsyncSession, user: User, base_limit: int, max_limit: int) -> int:
    """Return per second click limit taking into account equipment bonuses."""

    row = await session.execute(
        select(Item.bonus_value)
        .join(UserEquipment, UserEquipment.item_id == Item.id)
        .where(and_(UserEquipment.user_id == user.id, Item.slot == "chair"))
    )
    bonus = row.scalar_one_or_none() or 0
    return min(max_limit, base_limit + int(bonus))
