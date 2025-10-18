"""Start command and global navigation handlers."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.constants import RU
from bot.database.base import async_session_maker
from bot.keyboards.reply import kb_main_menu
from bot.services.users import ensure_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Initialize user profile and show main menu."""

    async with async_session_maker() as session:
        async with session.begin():
            await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
    await message.answer(RU.WELCOME, reply_markup=kb_main_menu())


@router.message(F.text == RU.BTN_MENU)
async def back_to_menu(message: Message) -> None:
    """Return user to the main menu and apply passive income."""

    async with async_session_maker() as session:
        async with session.begin():
            await ensure_user(session, message.from_user.id, message.from_user.first_name or "")
    await message.answer(RU.MENU_HINT, reply_markup=kb_main_menu())
