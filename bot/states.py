"""FSM states used by handlers."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrdersState(StatesGroup):
    browsing = State()
    confirm = State()


class ShopState(StatesGroup):
    root = State()
    boosts = State()
    equipment = State()
    confirm_boost = State()
    confirm_item = State()


class TeamState(StatesGroup):
    browsing = State()
    confirm = State()


class WardrobeState(StatesGroup):
    browsing = State()
    equip_confirm = State()


class ProfileState(StatesGroup):
    confirm_cancel = State()
