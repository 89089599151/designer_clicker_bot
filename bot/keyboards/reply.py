"""Reply keyboard builders used across handlers."""
from __future__ import annotations

from typing import Iterable, List

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.constants import RU


def _menu_button(text: str) -> KeyboardButton:
    return KeyboardButton(text=text)


def kb_main_menu() -> ReplyKeyboardMarkup:
    """Main navigation keyboard."""

    keyboard = [
        [_menu_button(RU.BTN_CLICK), _menu_button(RU.BTN_ORDERS)],
        [_menu_button(RU.BTN_SHOP), _menu_button(RU.BTN_TEAM)],
        [_menu_button(RU.BTN_WARDROBE), _menu_button(RU.BTN_PROFILE)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def kb_menu_only() -> ReplyKeyboardMarkup:
    """Keyboard with a single "menu" button."""

    keyboard = [[_menu_button(RU.BTN_MENU)]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def kb_numeric_page(numbers: Iterable[int], show_prev: bool, show_next: bool) -> ReplyKeyboardMarkup:
    """Keyboard with numeric selection and optional navigation."""

    number_buttons = [_menu_button(str(num)) for num in numbers]
    keyboard: List[List[KeyboardButton]] = [number_buttons]
    nav_row: List[KeyboardButton] = []
    if show_prev:
        nav_row.append(_menu_button(RU.BTN_PREV))
    if show_next:
        nav_row.append(_menu_button(RU.BTN_NEXT))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([_menu_button(RU.BTN_MENU)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def kb_confirm(confirm_text: str = RU.BTN_CONFIRM) -> ReplyKeyboardMarkup:
    """Confirmation keyboard with cancel and menu buttons."""

    keyboard = [
        [_menu_button(confirm_text), _menu_button(RU.BTN_CANCEL)],
        [_menu_button(RU.BTN_MENU)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def kb_shop_menu() -> ReplyKeyboardMarkup:
    """Keyboard for selecting shop sections."""

    keyboard = [
        [_menu_button(RU.BTN_BOOSTS), _menu_button(RU.BTN_EQUIPMENT)],
        [_menu_button(RU.BTN_MENU)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def kb_profile_menu(has_active_order: bool) -> ReplyKeyboardMarkup:
    """Profile actions keyboard that toggles cancel order option."""

    row: List[KeyboardButton] = [_menu_button(RU.BTN_DAILY)]
    if has_active_order:
        row.append(_menu_button(RU.BTN_CANCEL_ORDER))
    keyboard = [row, [_menu_button(RU.BTN_MENU)]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
