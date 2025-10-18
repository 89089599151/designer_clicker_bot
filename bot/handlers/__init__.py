"""Aggregate all routers for the bot."""
from __future__ import annotations

from aiogram import Router

from bot.handlers import click, orders, profile, shop, start, team, wardrobe


def setup_routers() -> Router:
    """Compose the root router with all feature routers."""

    router = Router()
    router.include_router(start.router)
    router.include_router(click.router)
    router.include_router(orders.router)
    router.include_router(shop.router)
    router.include_router(team.router)
    router.include_router(wardrobe.router)
    router.include_router(profile.router)
    return router
