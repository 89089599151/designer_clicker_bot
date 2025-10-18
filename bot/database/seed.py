"""Database seeding helpers."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Boost, Item, Order, TeamMember

SEED_ORDERS = [
    {"title": "Визитка для фрилансера", "base_clicks": 100, "min_level": 1},
    {"title": "Обложка для VK", "base_clicks": 180, "min_level": 1},
    {"title": "Логоип для кафе", "base_clicks": 300, "min_level": 2},
    {"title": "Лендинг (1 экран)", "base_clicks": 600, "min_level": 3},
    {"title": "Брендбук (мини)", "base_clicks": 1200, "min_level": 5},
    {"title": "Редизайн логотипа", "base_clicks": 800, "min_level": 4},
]

SEED_BOOSTS = [
    {"code": "cp_plus_1", "name": "Клик +1", "type": "cp", "base_cost": 100, "growth": 1.25, "step_value": 1},
    {"code": "reward_mul_10", "name": "Награда +10%", "type": "reward", "base_cost": 300, "growth": 1.18, "step_value": 0.10},
    {"code": "passive_mul_10", "name": "Пассивный доход +10%", "type": "passive", "base_cost": 400, "growth": 1.18, "step_value": 0.10},
]

SEED_TEAM = [
    {"code": "junior", "name": "Junior Designer", "base_income_per_min": 4, "base_cost": 100},
    {"code": "middle", "name": "Middle Designer", "base_income_per_min": 10, "base_cost": 300},
    {"code": "senior", "name": "Senior Designer", "base_income_per_min": 22, "base_cost": 800},
    {"code": "pm", "name": "Project Manager", "base_income_per_min": 35, "base_cost": 1200},
]

SEED_ITEMS = [
    {"code": "laptop_t1", "name": "Ноутбук T1", "slot": "laptop", "tier": 1, "bonus_type": "cp_pct", "bonus_value": 0.05, "price": 250, "min_level": 1},
    {"code": "laptop_t2", "name": "Ноутбук T2", "slot": "laptop", "tier": 2, "bonus_type": "cp_pct", "bonus_value": 0.10, "price": 500, "min_level": 2},
    {"code": "laptop_t3", "name": "Ноутбук T3", "slot": "laptop", "tier": 3, "bonus_type": "cp_pct", "bonus_value": 0.15, "price": 900, "min_level": 3},
    {"code": "phone_t1", "name": "Смартфон T1", "slot": "phone", "tier": 1, "bonus_type": "passive_pct", "bonus_value": 0.03, "price": 200, "min_level": 1},
    {"code": "phone_t2", "name": "Смартфон T2", "slot": "phone", "tier": 2, "bonus_type": "passive_pct", "bonus_value": 0.06, "price": 400, "min_level": 2},
    {"code": "phone_t3", "name": "Смартфон T3", "slot": "phone", "tier": 3, "bonus_type": "passive_pct", "bonus_value": 0.10, "price": 700, "min_level": 3},
    {"code": "tablet_t1", "name": "Планшет T1", "slot": "tablet", "tier": 1, "bonus_type": "req_clicks_pct", "bonus_value": 0.05, "price": 220, "min_level": 1},
    {"code": "tablet_t2", "name": "Планшет T2", "slot": "tablet", "tier": 2, "bonus_type": "req_clicks_pct", "bonus_value": 0.09, "price": 480, "min_level": 2},
    {"code": "monitor_t1", "name": "Монитор T1", "slot": "monitor", "tier": 1, "bonus_type": "reward_pct", "bonus_value": 0.05, "price": 260, "min_level": 1},
    {"code": "monitor_t2", "name": "Монитор T2", "slot": "monitor", "tier": 2, "bonus_type": "reward_pct", "bonus_value": 0.09, "price": 520, "min_level": 2},
    {"code": "chair_t1", "name": "Стул T1", "slot": "chair", "tier": 1, "bonus_type": "ratelimit_plus", "bonus_value": 1, "price": 300, "min_level": 1},
    {"code": "chair_t2", "name": "Стул T2", "slot": "chair", "tier": 2, "bonus_type": "ratelimit_plus", "bonus_value": 2, "price": 600, "min_level": 2},
]


async def seed_if_needed(session: AsyncSession) -> None:
    """Populate static lookup tables if they are empty."""

    if (await session.scalar(select(func.count()).select_from(Order))) == 0:
        for data in SEED_ORDERS:
            session.add(Order(**data))

    if (await session.scalar(select(func.count()).select_from(Boost))) == 0:
        for data in SEED_BOOSTS:
            session.add(Boost(**data))

    if (await session.scalar(select(func.count()).select_from(TeamMember))) == 0:
        for data in SEED_TEAM:
            session.add(TeamMember(**data))

    if (await session.scalar(select(func.count()).select_from(Item))) == 0:
        for data in SEED_ITEMS:
            session.add(Item(**data))
