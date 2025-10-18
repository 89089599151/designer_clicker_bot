# -*- coding: utf-8 -*-
"""
Designer Clicker Bot — single-file edition (patched)
===================================================
Полностью рабочий Telegram-кликер «Дизайнер» в одном файле.
Технологии: Python 3.11+ (совместимо с 3.12), aiogram 3.x, SQLAlchemy 2.x (async), SQLite (aiosqlite).

Как запустить:
1) Установите зависимости:
   pip install aiogram SQLAlchemy[asyncio] aiosqlite pydantic python-dotenv

2) Создайте .env рядом с этим файлом и укажите BOT_TOKEN:
   BOT_TOKEN=1234567890:AAFxY-YourRealTelegramBotTokenHere
   # необязательно:
   DATABASE_URL=sqlite+aiosqlite:///./designer.db
   DAILY_BONUS_RUB=100

3) Запуск:
   python designer_clicker_bot.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from math import floor
from typing import AsyncIterator, Deque, Dict, List, Literal, Optional, Tuple

# --- .env ---
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# --- aiogram ---
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# --- SQLAlchemy ---
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
    select,
    func,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.exc import IntegrityError

# ----------------------------------------------------------------------------
# Конфиг и логирование
# ----------------------------------------------------------------------------


@dataclass
class Settings:
    """Простые настройки из окружения. Pydantic не обязателен, чтобы сэкономить импорт."""
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./designer.db")
    DAILY_BONUS_RUB: int = int(os.getenv("DAILY_BONUS_RUB", "100"))
    BASE_ADMIN_ID: int = int(os.getenv("BASE_ADMIN_ID", "0"))


SETTINGS = Settings()


MAX_OFFLINE_SECONDS = 12 * 60 * 60
BASE_CLICK_LIMIT = 10
MAX_CLICK_LIMIT = 15


class JsonLogFormatter(logging.Formatter):
    """Formatter that emits structured JSON lines for easier ingestion."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - short implementation
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload or key in {
                "args",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            payload.setdefault("extras", {})[key] = value
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonLogFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("designer_clicker_single")

# ----------------------------------------------------------------------------
# I18N — русские строки и подписи кнопок
# ----------------------------------------------------------------------------


class RU:
    # Главное меню
    BTN_CLICK = "Клик"
    BTN_ORDERS = "Заказы"
    BTN_SHOP = "Магазин"
    BTN_TEAM = "Команда"
    BTN_WARDROBE = "Гардероб"
    BTN_PROFILE = "Профиль"

    # Общие
    BTN_MENU = "В меню"
    BTN_PREV = "◀️ Назад"
    BTN_NEXT = "Вперёд ▶️"
    BTN_TAKE = "Взять заказ"
    BTN_CANCEL = "Отмена"
    BTN_CONFIRM = "Подтвердить"
    BTN_EQUIP = "Экипировать"
    BTN_BUY = "Купить"
    BTN_UPGRADE = "Повысить"
    BTN_BOOSTS = "Бусты"
    BTN_EQUIPMENT = "Экипировка"
    BTN_DAILY = "Ежедневный бонус"
    BTN_CANCEL_ORDER = "Отменить заказ"

    # Сообщения
    BOT_STARTED = "Бот запущен."
    WELCOME = "Добро пожаловать в «Дизайнер»! На старте у вас уже 200 ₽ — выберите действие."
    MENU_HINT = "Главное меню: выберите направление развития."
    TOO_FAST = "Темп слишком высокий. Дождитесь восстановления лимита."
    NO_ACTIVE_ORDER = "У вас нет активного заказа. Откройте раздел «Заказы»."
    CLICK_PROGRESS = "Прогресс: {cur}/{req} кликов ({pct}%)."
    ORDER_TAKEN = "Вы взяли заказ «{title}». Удачи!"
    ORDER_ALREADY = "У вас уже есть активный заказ."
    ORDER_DONE = "Заказ завершён! Награда: {rub} ₽, XP: {xp}."
    ORDER_CANCELED = "Заказ отменён. Прогресс сброшен."
    INSUFFICIENT_FUNDS = "Недостаточно средств."
    PURCHASE_OK = "Покупка успешна."
    UPGRADE_OK = "Повышение выполнено."
    EQUIP_OK = "Экипировано."
    EQUIP_NOITEM = "Сначала купите предмет."
    DAILY_OK = "Начислен ежедневный бонус: {rub} ₽."
    DAILY_WAIT = "Бонус уже получен. Загляните позже."
    PROFILE = (
        "Профиль\n"
        "Уровень: {lvl}\nXP: {xp}/{xp_need}\n"
        "Баланс: {rub} ₽\n"
        "CP: {cp}\n"
        "Пассивный доход: {pm}/мин\n"
        "Текущий заказ: {order}"
    )
    TEAM_HEADER = "Команда (доход/мин, уровень, цена повышения):"
    SHOP_HEADER = "Магазин: выберите раздел для прокачки."
    WARDROBE_HEADER = "Гардероб: слоты и доступные предметы."
    ORDERS_HEADER = "Доступные заказы (введите номер для выбора):"

    # Форматирование
    CURRENCY = "₽"


# ----------------------------------------------------------------------------
# Клавиатуры (только ReplyKeyboard)
# ----------------------------------------------------------------------------

def kb_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=RU.BTN_CLICK), KeyboardButton(text=RU.BTN_ORDERS)],
        [KeyboardButton(text=RU.BTN_SHOP), KeyboardButton(text=RU.BTN_TEAM)],
        [KeyboardButton(text=RU.BTN_WARDROBE), KeyboardButton(text=RU.BTN_PROFILE)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False, selective=False
    )


def kb_menu_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=RU.BTN_MENU)]],
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )


def kb_numeric_page(show_prev: bool, show_next: bool) -> ReplyKeyboardMarkup:
    numbers = [KeyboardButton(text=str(i)) for i in range(1, 6)]
    nav_row: List[KeyboardButton] = []
    if show_prev:
        nav_row.append(KeyboardButton(text=RU.BTN_PREV))
    if show_next:
        nav_row.append(KeyboardButton(text=RU.BTN_NEXT))
    kb = [numbers]
    if nav_row:
        kb.append(nav_row)
    kb.append([KeyboardButton(text=RU.BTN_MENU)])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)


def kb_confirm(confirm_text: str = RU.BTN_CONFIRM) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=confirm_text), KeyboardButton(text=RU.BTN_CANCEL)],
            [KeyboardButton(text=RU.BTN_MENU)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def kb_shop_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RU.BTN_BOOSTS), KeyboardButton(text=RU.BTN_EQUIPMENT)],
            [KeyboardButton(text=RU.BTN_MENU)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def kb_profile_menu(has_active_order: bool) -> ReplyKeyboardMarkup:
    row1 = [KeyboardButton(text=RU.BTN_DAILY)]
    if has_active_order:
        row1.append(KeyboardButton(text=RU.BTN_CANCEL_ORDER))
    return ReplyKeyboardMarkup(
        keyboard=[row1, [KeyboardButton(text=RU.BTN_MENU)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ----------------------------------------------------------------------------
# Обёртка обработчиков
# ----------------------------------------------------------------------------

ERROR_MESSAGE = "Произошла ошибка. Попробуйте позже."


def safe_handler(func):
    """Обёртка для обработчиков сообщений, чтобы логировать ошибки и отвечать пользователю."""

    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        try:
            return await func(message, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - важно логировать любые сбои
            logger.exception("Unhandled error in %s", func.__name__, exc_info=exc)
            if isinstance(message, Message):
                try:
                    await message.answer(ERROR_MESSAGE, reply_markup=kb_main_menu())
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to send error notification to user")

    return wrapper


# ----------------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------------

def utcnow() -> datetime:
    """Return the current UTC time as naive datetime in UTC zone.

    SQLite does not preserve timezone info in ``DateTime`` columns reliably,
    therefore values loaded back are usually naive. Returning a naive datetime
    keeps arithmetic consistent when we subtract stored values from the current
    timestamp.
    """

    return datetime.utcnow()


def ensure_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to naive UTC representation."""

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def slice_page(items: List, page: int, page_size: int = 5) -> Tuple[List, bool, bool]:
    """Return sublist for pagination along with availability of prev/next pages."""

    start = page * page_size
    end = start + page_size
    sub = items[start:end]
    has_prev = page > 0
    has_next = end < len(items)
    return sub, has_prev, has_next


# ----------------------------------------------------------------------------
# ORM модели
# ----------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    balance: Mapped[int] = mapped_column(Integer, default=200)
    cp_base: Mapped[int] = mapped_column(Integer, default=1)  # базовая сила клика
    reward_mul: Mapped[float] = mapped_column(Float, default=0.0)  # добавочный % к награде (0.10=+10%)
    passive_mul: Mapped[float] = mapped_column(Float, default=0.0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    daily_bonus_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    orders: Mapped[List["UserOrder"]] = relationship(back_populates="user")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    base_clicks: Mapped[int] = mapped_column(Integer)
    min_level: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (Index("ix_orders_min_level", "min_level"),)


class UserOrder(Base):
    __tablename__ = "user_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    progress_clicks: Mapped[int] = mapped_column(Integer, default=0)
    required_clicks: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_snapshot_mul: Mapped[float] = mapped_column(Float, default=1.0)

    user: Mapped["User"] = relationship(back_populates="orders")
    order: Mapped["Order"] = relationship()
    __table_args__ = (
        Index("ix_user_orders_active", "user_id", "finished", "canceled"),
    )


class Boost(Base):
    __tablename__ = "boosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[Literal["cp", "reward", "passive"]] = mapped_column(String(20))
    base_cost: Mapped[int] = mapped_column(Integer)
    growth: Mapped[float] = mapped_column(Float)
    step_value: Mapped[float] = mapped_column(Float)


class UserBoost(Base):
    __tablename__ = "user_boosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    boost_id: Mapped[int] = mapped_column(ForeignKey("boosts.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "boost_id", name="uq_user_boost"),)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    base_income_per_min: Mapped[float] = mapped_column(Float)
    base_cost: Mapped[int] = mapped_column(Integer)


class UserTeam(Base):
    __tablename__ = "user_team"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0 — не нанят

    __table_args__ = (UniqueConstraint("user_id", "member_id", name="uq_user_team"),)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slot: Mapped[Literal["laptop", "phone", "tablet", "monitor", "chair"]] = mapped_column(String(20))
    tier: Mapped[int] = mapped_column(Integer)
    bonus_type: Mapped[Literal["cp_pct", "passive_pct", "req_clicks_pct", "reward_pct", "ratelimit_plus"]] = mapped_column(String(30))
    bonus_value: Mapped[float] = mapped_column(Float)
    price: Mapped[int] = mapped_column(Integer)
    min_level: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (Index("ix_items_slot_tier", "slot", "tier"),)


class UserItem(Base):
    __tablename__ = "user_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_user_item"),)


class UserEquipment(Base):
    __tablename__ = "user_equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[Literal["laptop", "phone", "tablet", "monitor", "chair"]] = mapped_column(String(20))
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_user_slot"),)


class EconomyLog(Base):
    __tablename__ = "economy_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_economy_user_created", "user_id", "created_at"),)


# ----------------------------------------------------------------------------
# Подключение к БД
# ----------------------------------------------------------------------------

engine = create_async_engine(SETTINGS.DATABASE_URL, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_models() -> None:
    """Create database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope for database work with automatic commit/rollback."""
    async with async_session_maker() as session:
        try:
            async with session.begin():
                yield session
        except Exception:
            logger.exception("Session rollback due to error.")
            raise


async def prepare_database() -> None:
    """Ensure that database schema and seed data are initialized exactly once."""
    async with session_scope() as session:
        await seed_if_needed(session)


# ----------------------------------------------------------------------------
# Сиды данных (встроенные)
# ----------------------------------------------------------------------------

SEED_ORDERS = [
    {"title": "Визитка для фрилансера", "base_clicks": 100, "min_level": 1},
    {"title": "Обложка для VK", "base_clicks": 180, "min_level": 1},
    {"title": "Логотип для кафе", "base_clicks": 300, "min_level": 2},
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

    {"code": "tablet_t1", "name": "Планшет T1", "slot": "tablet", "tier": 1, "bonus_type": "req_clicks_pct", "bonus_value": 0.02, "price": 300, "min_level": 1},
    {"code": "tablet_t2", "name": "Планшет T2", "slot": "tablet", "tier": 2, "bonus_type": "req_clicks_pct", "bonus_value": 0.04, "price": 600, "min_level": 2},

    {"code": "monitor_t1", "name": "Монитор T1", "slot": "monitor", "tier": 1, "bonus_type": "reward_pct", "bonus_value": 0.04, "price": 350, "min_level": 1},
    {"code": "monitor_t2", "name": "Монитор T2", "slot": "monitor", "tier": 2, "bonus_type": "reward_pct", "bonus_value": 0.08, "price": 700, "min_level": 2},

    {"code": "chair_t1", "name": "Стул T1", "slot": "chair", "tier": 1, "bonus_type": "ratelimit_plus", "bonus_value": 0, "price": 150, "min_level": 1},
    {"code": "chair_t2", "name": "Стул T2", "slot": "chair", "tier": 2, "bonus_type": "ratelimit_plus", "bonus_value": 1, "price": 400, "min_level": 2},
    {"code": "chair_t3", "name": "Стул T3", "slot": "chair", "tier": 3, "bonus_type": "ratelimit_plus", "bonus_value": 1, "price": 600, "min_level": 3},
    {"code": "chair_t4", "name": "Стул T4", "slot": "chair", "tier": 4, "bonus_type": "ratelimit_plus", "bonus_value": 2, "price": 1000, "min_level": 4},
]


async def seed_if_needed(session: AsyncSession) -> None:
    """Идемпотентная загрузка сидов при первом старте."""
    # Заказы
    cnt = (await session.execute(select(func.count()).select_from(Order))).scalar_one()
    if cnt == 0:
        for d in SEED_ORDERS:
            session.add(Order(title=d["title"], base_clicks=d["base_clicks"], min_level=d["min_level"]))
    # Бусты
    cnt = (await session.execute(select(func.count()).select_from(Boost))).scalar_one()
    if cnt == 0:
        for d in SEED_BOOSTS:
            session.add(Boost(code=d["code"], name=d["name"], type=d["type"],
                              base_cost=d["base_cost"], growth=d["growth"], step_value=d["step_value"]))
    # Команда
    cnt = (await session.execute(select(func.count()).select_from(TeamMember))).scalar_one()
    if cnt == 0:
        for d in SEED_TEAM:
            session.add(TeamMember(code=d["code"], name=d["name"],
                                   base_income_per_min=d["base_income_per_min"], base_cost=d["base_cost"]))
    # Предметы
    cnt = (await session.execute(select(func.count()).select_from(Item))).scalar_one()
    if cnt == 0:
        for d in SEED_ITEMS:
            session.add(Item(code=d["code"], name=d["name"], slot=d["slot"], tier=d["tier"],
                             bonus_type=d["bonus_type"], bonus_value=d["bonus_value"],
                             price=d["price"], min_level=d["min_level"]))
    # Санируем старые записи user_orders без снимка множителя
    await session.execute(
        update(UserOrder)
        .where(UserOrder.reward_snapshot_mul <= 0)
        .values(reward_snapshot_mul=1.0)
    )


# ----------------------------------------------------------------------------
# Экономика: формулы и сервисы
# ----------------------------------------------------------------------------

def xp_to_level(n: int) -> int:
    return 100 * n * n


def upgrade_cost(base: int, growth: float, n: int) -> int:
    return round(base * (growth ** (n - 1)))


def required_clicks(base_clicks: int, level: int) -> int:
    return int(round(base_clicks * (1 + 0.15 * floor(level / 5))))


def base_reward_from_required(req: int, reward_mul: float = 1.0) -> int:
    return int(round(req * 0.6 * reward_mul))


async def get_user_stats(session: AsyncSession, user: User) -> dict:
    """Return aggregated user stats from boosts and equipment."""

    rows = (
        await session.execute(
            select(Boost.type, UserBoost.level, Boost.step_value)
            .select_from(UserBoost)
            .join(Boost, Boost.id == UserBoost.boost_id)
            .where(UserBoost.user_id == user.id)
        )
    ).all()
    cp_add = 0
    reward_add = 0.0
    passive_add = 0.0
    for btype, lvl, step in rows:
        if btype == "cp":
            cp_add += int(lvl * step)
        elif btype == "reward":
            reward_add += lvl * step
        elif btype == "passive":
            passive_add += lvl * step
    # Экип
    items = (
        await session.execute(
            select(Item.bonus_type, Item.bonus_value)
            .join(UserEquipment, UserEquipment.item_id == Item.id)
            .where(UserEquipment.user_id == user.id, UserEquipment.item_id.is_not(None))
        )
    ).all()
    cp_pct = 0.0
    passive_pct = 0.0
    req_clicks_pct = 0.0
    reward_pct = 0.0
    ratelimit_plus = 0
    for btype, val in items:
        if btype == "cp_pct":
            cp_pct += val
        elif btype == "passive_pct":
            passive_pct += val
        elif btype == "req_clicks_pct":
            req_clicks_pct += val
        elif btype == "reward_pct":
            reward_pct += val
        elif btype == "ratelimit_plus":
            ratelimit_plus += int(val)

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


def team_income_per_min(base_per_min: float, level: int) -> float:
    """Calculate per-minute income from a team member for the given level."""

    if level <= 0:
        return 0.0
    return base_per_min * (1 + 0.25 * (level - 1))


async def calc_passive_income_rate(session: AsyncSession, user: User, passive_mul_total: float) -> float:
    """Return passive income in currency per second accounting for multipliers."""

    rows = (
        await session.execute(
            select(TeamMember.base_income_per_min, UserTeam.level)
            .join(UserTeam, TeamMember.id == UserTeam.member_id)
            .where(UserTeam.user_id == user.id)
        )
    ).all()
    per_min = sum(team_income_per_min(b, lvl) for b, lvl in rows)
    return (per_min / 60.0) * passive_mul_total


async def apply_offline_income(session: AsyncSession, user: User) -> int:
    """Apply passive income accumulated since the last interaction."""

    now = utcnow()
    last_seen = ensure_naive(user.last_seen) or now
    delta_raw = max(0.0, (now - last_seen).total_seconds())
    delta = min(delta_raw, MAX_OFFLINE_SECONDS)
    user.last_seen = now
    user.updated_at = now
    stats = await get_user_stats(session, user)
    rate = await calc_passive_income_rate(session, user, stats["passive_mul_total"])
    amount = int(rate * delta)
    if delta_raw > MAX_OFFLINE_SECONDS:
        logger.info(
            "Offline income capped",
            extra={"tg_id": user.tg_id, "seconds_raw": int(delta_raw), "seconds_used": int(delta)},
        )
    if amount > 0:
        user.balance += amount
        session.add(
            EconomyLog(
                user_id=user.id,
                type="passive",
                amount=amount,
                meta={"sec": int(delta), "sec_raw": int(delta_raw)},
                created_at=now,
            )
        )
        logger.debug("Offline income for user %s: +%s", user.tg_id, amount)
    return amount


def snapshot_required_clicks(order: Order, user_level: int, req_clicks_pct: float) -> int:
    """Calculate the effective clicks required for an order based on user stats."""

    base_req = required_clicks(order.base_clicks, user_level)
    reduced = int(round(base_req * (1 - req_clicks_pct)))
    return max(1, reduced)


def finish_order_reward(required_clicks_snapshot: int, reward_snapshot_mul: float) -> int:
    """Return reward amount for completed order based on snapshot multipliers."""

    mul = max(1.0, reward_snapshot_mul)
    return base_reward_from_required(required_clicks_snapshot, mul)


async def ensure_no_active_order(session: AsyncSession, user: User) -> bool:
    """Check that user does not have unfinished order."""

    stmt = select(UserOrder).where(
        UserOrder.user_id == user.id,
        UserOrder.finished.is_(False),
        UserOrder.canceled.is_(False),
    )
    return (await session.scalar(stmt)) is None


async def get_active_order(session: AsyncSession, user: User) -> Optional[UserOrder]:
    """Return current active order for user if any."""

    stmt = select(UserOrder).where(
        UserOrder.user_id == user.id,
        UserOrder.finished.is_(False),
        UserOrder.canceled.is_(False),
    )
    return await session.scalar(stmt)


async def add_xp_and_levelup(user: User, xp_gain: int) -> None:
    """Apply XP gain to user and increment level when threshold reached."""

    user.xp += xp_gain
    lvl = user.level
    while user.xp >= xp_to_level(lvl):
        user.xp -= xp_to_level(lvl)
        lvl += 1
    user.level = lvl


# ----------------------------------------------------------------------------
# Анти-флуд (middleware)
# ----------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window rate limiter per Telegram user."""

    def __init__(self) -> None:
        self._events: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=100))

    def allow(self, user_id: int, limit_per_sec: int, now: Optional[float] = None) -> bool:
        """Return True if event allowed under given rate, False otherwise."""

        t = time.monotonic() if now is None else now
        dq = self._events[user_id]
        while dq and t - dq[0] > 1.0:
            dq.popleft()
        if len(dq) >= limit_per_sec:
            return False
        dq.append(t)
        return True


class RateLimitMiddleware(BaseMiddleware):
    """Middleware ограничения кликов/сек. Поднимает предупреждение и блокирует обработчик при превышении."""
    def __init__(self, limit_getter):
        super().__init__()
        self.limiter = RateLimiter()
        self.limit_getter = limit_getter

    async def __call__(self, handler, event: Message, data):
        try:
            if isinstance(event, Message) and (event.text or "") == RU.BTN_CLICK:
                tg_id = event.from_user.id
                limit = await self.limit_getter(tg_id)
                if not self.limiter.allow(tg_id, limit):
                    logger.debug("Rate limit hit", extra={"tg_id": tg_id, "limit": limit})
                    await event.answer(RU.TOO_FAST)
                    return
        except Exception as e:
            logger.exception("RateLimitMiddleware error: %s", e)
        return await handler(event, data)


async def get_user_click_limit(tg_id: int) -> int:
    """Базовый лимит 10/сек + бонус от экипировки стула (до 15)."""

    async with session_scope() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return BASE_CLICK_LIMIT
        stats = await get_user_stats(session, user)
        limit = BASE_CLICK_LIMIT + int(stats.get("ratelimit_plus", 0))
    return max(1, min(MAX_CLICK_LIMIT, limit))


# ----------------------------------------------------------------------------
# FSM состояния
# ----------------------------------------------------------------------------

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


# ----------------------------------------------------------------------------
# Роутер и обработчики
# ----------------------------------------------------------------------------

router = Router()


async def get_or_create_user(tg_id: int, first_name: str) -> User:
    """Fetch existing user or create a new record."""

    async with session_scope() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
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
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                logger.warning(
                    "Race while creating user", extra={"tg_id": tg_id}
                )
                return await get_or_create_user(tg_id, first_name)
            for slot in ["laptop", "phone", "tablet", "monitor", "chair"]:
                session.add(UserEquipment(user_id=user.id, slot=slot, item_id=None))
            logger.info("New user created", extra={"tg_id": tg_id, "user_id": user.id})
        else:
            await apply_offline_income(session, user)
            logger.debug("Existing user resumed session", extra={"tg_id": tg_id})
        return user


async def get_user_by_tg(session: AsyncSession, tg_id: int) -> Optional[User]:
    """Load user entity by Telegram identifier."""

    return await session.scalar(select(User).where(User.tg_id == tg_id))


async def ensure_user_loaded(session: AsyncSession, message: Message) -> Optional[User]:
    """Return user for message or notify user to start the bot."""

    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Нажмите /start", reply_markup=kb_main_menu())
        return None
    return user


@router.message(CommandStart())
@safe_handler
async def cmd_start(message: Message):
    user = await get_or_create_user(message.from_user.id, message.from_user.first_name or "")
    logger.info("User issued /start", extra={"tg_id": message.from_user.id, "user_id": user.id})
    await message.answer(RU.WELCOME, reply_markup=kb_main_menu())


@router.message(F.text == RU.BTN_MENU)
@safe_handler
async def back_to_menu(message: Message):
    async with session_scope() as session:
        user = await get_user_by_tg(session, message.from_user.id)
        if user:
            await apply_offline_income(session, user)
    await message.answer(RU.MENU_HINT, reply_markup=kb_main_menu())


# --- Клик ---

@router.message(F.text == RU.BTN_CLICK)
@safe_handler
async def handle_click(message: Message):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            return
        await apply_offline_income(session, user)
        active = await get_active_order(session, user)
        if not active:
            await message.answer(RU.NO_ACTIVE_ORDER)
            return
        stats = await get_user_stats(session, user)
        cp = stats["cp"]
        prev = active.progress_clicks
        active.progress_clicks = min(active.required_clicks, active.progress_clicks + cp)
        if (active.progress_clicks // 10) > (prev // 10) or active.progress_clicks == active.required_clicks:
            pct = int(100 * active.progress_clicks / active.required_clicks)
            await message.answer(
                RU.CLICK_PROGRESS.format(cur=active.progress_clicks, req=active.required_clicks, pct=pct)
            )
        if active.progress_clicks >= active.required_clicks:
            reward = finish_order_reward(active.required_clicks, active.reward_snapshot_mul)
            xp_gain = int(round(active.required_clicks * 0.1))
            now = utcnow()
            user.balance += reward
            await add_xp_and_levelup(user, xp_gain)
            user.updated_at = now
            active.finished = True
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="order_finish",
                    amount=reward,
                    meta={"order_id": active.order_id},
                    created_at=now,
                )
            )
            logger.info(
                "Order finished",
                extra={
                    "tg_id": user.tg_id,
                    "user_id": user.id,
                    "order_id": active.order_id,
                    "reward": reward,
                },
            )
            await message.answer(RU.ORDER_DONE.format(rub=reward, xp=xp_gain))


# --- Заказы ---

def fmt_orders(orders: List[Order]) -> str:
    lines = [RU.ORDERS_HEADER, ""]
    for i, o in enumerate(orders, 1):
        lines.append(f"[{i}] {o.title} — мин. ур. {o.min_level}")
    return "\n".join(lines)


@router.message(F.text == RU.BTN_ORDERS)
@safe_handler
async def orders_root(message: Message, state: FSMContext):
    await state.set_state(OrdersState.browsing)
    await state.update_data(page=0)
    await _render_orders_page(message, state)


async def _render_orders_page(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        await apply_offline_income(session, user)
        all_orders = (
            await session.execute(
                select(Order)
                .where(Order.min_level <= user.level)
                .order_by(Order.min_level, Order.id)
            )
        ).scalars().all()
        data = await state.get_data()
        page = int(data.get("page", 0))
        sub, has_prev, has_next = slice_page(all_orders, page, 5)
        await message.answer(fmt_orders(sub), reply_markup=kb_numeric_page(has_prev, has_next))
        await state.update_data(order_ids=[o.id for o in sub], page=page)


@router.message(OrdersState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
@safe_handler
async def choose_order(message: Message, state: FSMContext):
    data = await state.get_data()
    ids = data.get("order_ids", [])
    idx = int(message.text) - 1
    if idx < 0 or idx >= len(ids):
        return
    order_id = ids[idx]
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        if not await ensure_no_active_order(session, user):
            await message.answer(RU.ORDER_ALREADY)
            return
        order = await session.scalar(select(Order).where(Order.id == order_id))
        if not order:
            await message.answer("Заказ не найден.", reply_markup=kb_menu_only())
            return
        stats = await get_user_stats(session, user)
        req = snapshot_required_clicks(order, user.level, stats["req_clicks_pct"])
        await state.set_state(OrdersState.confirm)
        await state.update_data(order_id=order_id, req=req)
        await message.answer(
            f"Взять заказ «{order.title}»?\nТребуемые клики: {req}", reply_markup=kb_confirm(RU.BTN_TAKE)
        )


@router.message(OrdersState.browsing, F.text == RU.BTN_PREV)
@safe_handler
async def orders_prev(message: Message, state: FSMContext):
    data = await state.get_data()
    page = max(0, int(data.get("page", 0)) - 1)
    await state.update_data(page=page)
    await _render_orders_page(message, state)


@router.message(OrdersState.browsing, F.text == RU.BTN_NEXT)
@safe_handler
async def orders_next(message: Message, state: FSMContext):
    data = await state.get_data()
    page = int(data.get("page", 0)) + 1
    await state.update_data(page=page)
    await _render_orders_page(message, state)


@router.message(OrdersState.confirm, F.text == RU.BTN_TAKE)
@safe_handler
async def take_order(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = int(data["order_id"])
    req = int(data["req"])
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        if not await ensure_no_active_order(session, user):
            await message.answer(RU.ORDER_ALREADY)
            await state.clear()
            return
        stats = await get_user_stats(session, user)
        session.add(
            UserOrder(
                user_id=user.id,
                order_id=order_id,
                progress_clicks=0,
                required_clicks=req,
                started_at=utcnow(),
                finished=False,
                canceled=False,
                reward_snapshot_mul=stats["reward_mul_total"],
            )
        )
        user.updated_at = utcnow()
        order = await session.scalar(select(Order).where(Order.id == order_id))
        if order:
            await message.answer(RU.ORDER_TAKEN.format(title=order.title), reply_markup=kb_menu_only())
        logger.info(
            "Order taken",
            extra={"tg_id": user.tg_id, "user_id": user.id, "order_id": order_id},
        )
    await state.clear()


@router.message(OrdersState.confirm, F.text == RU.BTN_CANCEL)
@safe_handler
async def take_cancel(message: Message, state: FSMContext):
    await state.clear()
    await orders_root(message, state)


# --- Магазин ---

@router.message(F.text == RU.BTN_SHOP)
@safe_handler
async def shop_root(message: Message, state: FSMContext):
    await state.set_state(ShopState.root)
    await message.answer(RU.SHOP_HEADER, reply_markup=kb_shop_menu())


def fmt_boosts(lines: List[str]) -> str:
    return "\n".join(lines) if lines else "Нет бустов."


async def render_boosts(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        await apply_offline_income(session, user)
        boosts = (
            await session.execute(select(Boost).order_by(Boost.id))
        ).scalars().all()
        levels = {
            b_id: lvl
            for b_id, lvl in (
                await session.execute(
                    select(UserBoost.boost_id, UserBoost.level).where(UserBoost.user_id == user.id)
                )
            ).all()
        }
        page = int((await state.get_data()).get("page", 0))
        sub, has_prev, has_next = slice_page(boosts, page, 5)
        lines = []
        for i, b in enumerate(sub, 1):
            lvl_next = levels.get(b.id, 0) + 1
            cost = upgrade_cost(b.base_cost, b.growth, lvl_next)
            lines.append(f"[{i}] {b.name} — ур. след. {lvl_next}, {cost} {RU.CURRENCY}")
        await message.answer(fmt_boosts(lines), reply_markup=kb_numeric_page(has_prev, has_next))
        await state.update_data(boost_ids=[b.id for b in sub], page=page)


@router.message(ShopState.root, F.text == RU.BTN_BOOSTS)
@safe_handler
async def shop_boosts(message: Message, state: FSMContext):
    await state.set_state(ShopState.boosts)
    await state.update_data(page=0)
    await render_boosts(message, state)


@router.message(ShopState.boosts, F.text.in_({"1", "2", "3", "4", "5"}))
@safe_handler
async def shop_choose_boost(message: Message, state: FSMContext):
    ids = (await state.get_data()).get("boost_ids", [])
    idx = int(message.text) - 1
    if idx < 0 or idx >= len(ids):
        return
    bid = ids[idx]
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        boost = await session.scalar(select(Boost).where(Boost.id == bid))
        if not boost:
            await message.answer("Буст не найден.", reply_markup=kb_menu_only())
            return
        user_boost = await session.scalar(
            select(UserBoost).where(UserBoost.user_id == user.id, UserBoost.boost_id == bid)
        )
        lvl_next = (user_boost.level if user_boost else 0) + 1
        cost = upgrade_cost(boost.base_cost, boost.growth, lvl_next)
        await message.answer(
            f"Купить буст «{boost.name}» (ур. след. {lvl_next}) за {cost} {RU.CURRENCY}?",
            reply_markup=kb_confirm(RU.BTN_BUY),
        )
    await state.set_state(ShopState.confirm_boost)
    await state.update_data(boost_id=bid)


@router.message(ShopState.boosts, F.text == RU.BTN_PREV)
@safe_handler
async def shop_boosts_prev(message: Message, state: FSMContext):
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await render_boosts(message, state)


@router.message(ShopState.boosts, F.text == RU.BTN_NEXT)
@safe_handler
async def shop_boosts_next(message: Message, state: FSMContext):
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await render_boosts(message, state)


@router.message(ShopState.confirm_boost, F.text == RU.BTN_BUY)
@safe_handler
async def shop_buy_boost(message: Message, state: FSMContext):
    bid = int((await state.get_data())["boost_id"])
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        boost = await session.scalar(select(Boost).where(Boost.id == bid))
        if not boost:
            await message.answer("Буст не найден.", reply_markup=kb_menu_only())
            await state.clear()
            return
        user_boost = await session.scalar(
            select(UserBoost).where(UserBoost.user_id == user.id, UserBoost.boost_id == bid)
        )
        lvl_next = (user_boost.level if user_boost else 0) + 1
        cost = upgrade_cost(boost.base_cost, boost.growth, lvl_next)
        if user.balance < cost:
            await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
        else:
            now = utcnow()
            user.balance -= cost
            user.updated_at = now
            if not user_boost:
                session.add(UserBoost(user_id=user.id, boost_id=bid, level=1))
            else:
                user_boost.level += 1
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="buy_boost",
                    amount=-cost,
                    meta={"boost": boost.code, "lvl": lvl_next},
                    created_at=now,
                )
            )
            logger.info(
                "Boost upgraded",
                extra={
                    "tg_id": user.tg_id,
                    "user_id": user.id,
                    "boost": boost.code,
                    "level": lvl_next,
                },
            )
            await message.answer(RU.PURCHASE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(ShopState.confirm_boost, F.text == RU.BTN_CANCEL)
@safe_handler
async def shop_cancel_boost(message: Message, state: FSMContext):
    await state.set_state(ShopState.boosts)
    await render_boosts(message, state)


# --- Магазин: экипировка ---

def fmt_items(items: List[Item]) -> str:
    if not items:
        return "Нет доступных предметов."
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] {it.name} ({it.slot}, T{it.tier}) — {it.price} {RU.CURRENCY}")
    return "\n".join(lines)


async def render_items(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        await apply_offline_income(session, user)
        items = (
            await session.execute(
                select(Item)
                .where(Item.min_level <= user.level)
                .order_by(Item.slot, Item.tier)
            )
        ).scalars().all()
        page = int((await state.get_data()).get("page", 0))
        sub, has_prev, has_next = slice_page(items, page, 5)
        await message.answer(fmt_items(sub), reply_markup=kb_numeric_page(has_prev, has_next))
        await state.update_data(item_ids=[it.id for it in sub], page=page)


@router.message(ShopState.root, F.text == RU.BTN_EQUIPMENT)
@safe_handler
async def shop_equipment(message: Message, state: FSMContext):
    await state.set_state(ShopState.equipment)
    await state.update_data(page=0)
    await render_items(message, state)


@router.message(ShopState.equipment, F.text.in_({"1", "2", "3", "4", "5"}))
@safe_handler
async def shop_choose_item(message: Message, state: FSMContext):
    item_ids = (await state.get_data()).get("item_ids", [])
    idx = int(message.text) - 1
    if idx < 0 or idx >= len(item_ids):
        return
    item_id = item_ids[idx]
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        it = await session.scalar(select(Item).where(Item.id == item_id))
        if not it:
            await message.answer("Предмет не найден.", reply_markup=kb_menu_only())
            return
        await message.answer(
            f"Купить предмет «{it.name}» за {it.price} {RU.CURRENCY}?",
            reply_markup=kb_confirm(RU.BTN_BUY),
        )
    await state.set_state(ShopState.confirm_item)
    await state.update_data(item_id=item_id)


@router.message(ShopState.equipment, F.text == RU.BTN_PREV)
@safe_handler
async def shop_items_prev(message: Message, state: FSMContext):
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await render_items(message, state)


@router.message(ShopState.equipment, F.text == RU.BTN_NEXT)
@safe_handler
async def shop_items_next(message: Message, state: FSMContext):
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await render_items(message, state)


@router.message(ShopState.confirm_item, F.text == RU.BTN_BUY)
@safe_handler
async def shop_buy_item(message: Message, state: FSMContext):
    item_id = int((await state.get_data())["item_id"])
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        item = await session.scalar(select(Item).where(Item.id == item_id))
        if not item:
            await message.answer("Предмет не найден.", reply_markup=kb_menu_only())
            await state.clear()
            return
        has = await session.scalar(
            select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item_id)
        )
        if has:
            await message.answer("Уже куплено.", reply_markup=kb_menu_only())
        elif user.balance < item.price:
            await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
        else:
            now = utcnow()
            user.balance -= item.price
            user.updated_at = now
            session.add(UserItem(user_id=user.id, item_id=item_id))
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="buy_item",
                    amount=-item.price,
                    meta={"item": item.code},
                    created_at=now,
                )
            )
            logger.info(
                "Item purchased",
                extra={"tg_id": user.tg_id, "user_id": user.id, "item": item.code},
            )
            await message.answer(RU.PURCHASE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(ShopState.confirm_item, F.text == RU.BTN_CANCEL)
@safe_handler
async def shop_cancel_item(message: Message, state: FSMContext):
    await state.set_state(ShopState.equipment)
    await render_items(message, state)


# --- Команда ---

def fmt_team(sub: List[TeamMember], levels: Dict[int, int], costs: Dict[int, int]) -> str:
    lines = [RU.TEAM_HEADER]
    for i, m in enumerate(sub, 1):
        lvl = levels.get(m.id, 0)
        income = team_income_per_min(m.base_income_per_min, lvl)
        lines.append(f"[{i}] {m.name}: {income:.0f}/мин, ур. {lvl}, цена повышения {costs[m.id]} {RU.CURRENCY}")
    return "\n".join(lines)


async def render_team(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        await apply_offline_income(session, user)
        members = (
            await session.execute(select(TeamMember).order_by(TeamMember.base_cost, TeamMember.id))
        ).scalars().all()
        levels = {
            mid: lvl
            for mid, lvl in (
                await session.execute(
                    select(UserTeam.member_id, UserTeam.level).where(UserTeam.user_id == user.id)
                )
            ).all()
        }
        costs = {m.id: int(round(m.base_cost * (1.22 ** max(0, levels.get(m.id, 0))))) for m in members}
        page = int((await state.get_data()).get("page", 0))
        sub, has_prev, has_next = slice_page(members, page, 5)
        await message.answer(fmt_team(sub, levels, costs), reply_markup=kb_numeric_page(has_prev, has_next))
        await state.update_data(member_ids=[m.id for m in sub], page=page)


@router.message(F.text == RU.BTN_TEAM)
@safe_handler
async def team_root(message: Message, state: FSMContext):
    await state.set_state(TeamState.browsing)
    await state.update_data(page=0)
    await render_team(message, state)


@router.message(TeamState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
@safe_handler
async def team_choose(message: Message, state: FSMContext):
    ids = (await state.get_data()).get("member_ids", [])
    idx = int(message.text) - 1
    if idx < 0 or idx >= len(ids):
        return
    mid = ids[idx]
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        member = await session.scalar(select(TeamMember).where(TeamMember.id == mid))
        if not member:
            await message.answer("Сотрудник не найден.", reply_markup=kb_menu_only())
            return
        await message.answer(f"Повысить «{member.name}»?", reply_markup=kb_confirm(RU.BTN_UPGRADE))
    await state.set_state(TeamState.confirm)
    await state.update_data(member_id=mid)


@router.message(TeamState.browsing, F.text == RU.BTN_PREV)
@safe_handler
async def team_prev(message: Message, state: FSMContext):
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await render_team(message, state)


@router.message(TeamState.browsing, F.text == RU.BTN_NEXT)
@safe_handler
async def team_next(message: Message, state: FSMContext):
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await render_team(message, state)


@router.message(TeamState.confirm, F.text == RU.BTN_UPGRADE)
@safe_handler
async def team_upgrade(message: Message, state: FSMContext):
    mid = int((await state.get_data())["member_id"])
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        member = await session.scalar(select(TeamMember).where(TeamMember.id == mid))
        if not member:
            await message.answer("Сотрудник не найден.", reply_markup=kb_menu_only())
            await state.clear()
            return
        team_entry = await session.scalar(
            select(UserTeam).where(UserTeam.user_id == user.id, UserTeam.member_id == mid)
        )
        lvl = team_entry.level if team_entry else 0
        cost = int(round(member.base_cost * (1.22 ** lvl)))
        if user.balance < cost:
            await message.answer(RU.INSUFFICIENT_FUNDS, reply_markup=kb_menu_only())
        else:
            now = utcnow()
            user.balance -= cost
            user.updated_at = now
            if not team_entry:
                session.add(UserTeam(user_id=user.id, member_id=mid, level=1))
            else:
                team_entry.level += 1
            session.add(
                EconomyLog(
                    user_id=user.id,
                    type="team_upgrade",
                    amount=-cost,
                    meta={"member": member.code, "lvl": lvl + 1},
                    created_at=now,
                )
            )
            logger.info(
                "Team upgraded",
                extra={
                    "tg_id": user.tg_id,
                    "user_id": user.id,
                    "member": member.code,
                    "level": lvl + 1,
                },
            )
            await message.answer(RU.UPGRADE_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(TeamState.confirm, F.text == RU.BTN_CANCEL)
@safe_handler
async def team_upgrade_cancel(message: Message, state: FSMContext):
    await state.set_state(TeamState.browsing)
    await render_team(message, state)


# --- Гардероб ---

def fmt_inventory(items: List[Item]) -> str:
    if not items:
        return "Инвентарь пуст."
    lines = [RU.WARDROBE_HEADER]
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] {it.name} ({it.slot}, T{it.tier})")
    return "\n".join(lines)


async def render_inventory(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        await apply_offline_income(session, user)
        items = (
            await session.execute(
                select(Item)
                .join(UserItem, UserItem.item_id == Item.id)
                .where(UserItem.user_id == user.id)
                .order_by(Item.slot, Item.tier)
            )
        ).scalars().all()
        page = int((await state.get_data()).get("page", 0))
        sub, has_prev, has_next = slice_page(items, page, 5)
        await message.answer(fmt_inventory(sub), reply_markup=kb_numeric_page(has_prev, has_next))
        await state.update_data(inv_ids=[it.id for it in sub], page=page)


@router.message(F.text == RU.BTN_WARDROBE)
@safe_handler
async def wardrobe_root(message: Message, state: FSMContext):
    await state.set_state(WardrobeState.browsing)
    await state.update_data(page=0)
    await render_inventory(message, state)


@router.message(WardrobeState.browsing, F.text.in_({"1", "2", "3", "4", "5"}))
@safe_handler
async def wardrobe_choose(message: Message, state: FSMContext):
    ids = (await state.get_data()).get("inv_ids", [])
    idx = int(message.text) - 1
    if idx < 0 or idx >= len(ids):
        return
    item_id = ids[idx]
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        it = await session.scalar(select(Item).where(Item.id == item_id))
        if not it:
            await message.answer("Предмет не найден.", reply_markup=kb_menu_only())
            return
        await message.answer(f"Экипировать «{it.name}»?", reply_markup=kb_confirm(RU.BTN_EQUIP))
    await state.set_state(WardrobeState.equip_confirm)
    await state.update_data(item_id=item_id)


@router.message(WardrobeState.browsing, F.text == RU.BTN_PREV)
@safe_handler
async def wardrobe_prev(message: Message, state: FSMContext):
    page = max(0, int((await state.get_data()).get("page", 0)) - 1)
    await state.update_data(page=page)
    await render_inventory(message, state)


@router.message(WardrobeState.browsing, F.text == RU.BTN_NEXT)
@safe_handler
async def wardrobe_next(message: Message, state: FSMContext):
    page = int((await state.get_data()).get("page", 0)) + 1
    await state.update_data(page=page)
    await render_inventory(message, state)


@router.message(WardrobeState.equip_confirm, F.text == RU.BTN_EQUIP)
@safe_handler
async def wardrobe_equip(message: Message, state: FSMContext):
    item_id = int((await state.get_data())["item_id"])
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            await state.clear()
            return
        item = await session.scalar(select(Item).where(Item.id == item_id))
        if not item:
            await message.answer("Предмет не найден.", reply_markup=kb_menu_only())
            await state.clear()
            return
        has = await session.scalar(
            select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item_id)
        )
        if not has:
            await message.answer(RU.EQUIP_NOITEM, reply_markup=kb_menu_only())
        else:
            now = utcnow()
            eq = await session.scalar(
                select(UserEquipment).where(UserEquipment.user_id == user.id, UserEquipment.slot == item.slot)
            )
            if not eq:
                session.add(UserEquipment(user_id=user.id, slot=item.slot, item_id=item.id))
            else:
                eq.item_id = item.id
            user.updated_at = now
            logger.info(
                "Item equipped",
                extra={"tg_id": user.tg_id, "user_id": user.id, "item": item.code},
            )
            await message.answer(RU.EQUIP_OK, reply_markup=kb_menu_only())
    await state.clear()


@router.message(WardrobeState.equip_confirm, F.text == RU.BTN_CANCEL)
@safe_handler
async def wardrobe_equip_cancel(message: Message, state: FSMContext):
    await state.set_state(WardrobeState.browsing)
    await render_inventory(message, state)


# --- Профиль ---

@router.message(F.text == RU.BTN_PROFILE)
@safe_handler
async def profile_show(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            return
        await apply_offline_income(session, user)
        stats = await get_user_stats(session, user)
        rate = await calc_passive_income_rate(session, user, stats["passive_mul_total"])
        active = await get_active_order(session, user)
        order_str = "нет"
        if active:
            ord_row = await session.scalar(select(Order).where(Order.id == active.order_id))
            if ord_row:
                order_str = f"{ord_row.title}: {active.progress_clicks}/{active.required_clicks}"
        xp_need = xp_to_level(user.level)
        text = RU.PROFILE.format(
            lvl=user.level,
            xp=user.xp,
            xp_need=xp_need,
            rub=user.balance,
            cp=stats["cp"],
            pm=int(rate * 60),
            order=order_str,
        )
        await message.answer(text, reply_markup=kb_profile_menu(has_active_order=bool(active)))


@router.message(F.text == RU.BTN_DAILY)
@safe_handler
async def profile_daily(message: Message):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            return
        now = utcnow()
        last_bonus = ensure_naive(user.daily_bonus_at)
        if last_bonus and (now - last_bonus) < timedelta(hours=24):
            await message.answer(RU.DAILY_WAIT, reply_markup=kb_main_menu())
            return
        user.daily_bonus_at = now
        user.balance += SETTINGS.DAILY_BONUS_RUB
        user.updated_at = now
        session.add(
            EconomyLog(
                user_id=user.id,
                type="daily_bonus",
                amount=SETTINGS.DAILY_BONUS_RUB,
                meta=None,
                created_at=now,
            )
        )
        logger.info("Daily bonus collected", extra={"tg_id": user.tg_id, "user_id": user.id})
        await message.answer(RU.DAILY_OK.format(rub=SETTINGS.DAILY_BONUS_RUB), reply_markup=kb_main_menu())


@router.message(F.text == RU.BTN_CANCEL_ORDER)
@safe_handler
async def profile_cancel_order(message: Message, state: FSMContext):
    async with session_scope() as session:
        user = await ensure_user_loaded(session, message)
        if not user:
            return
        active = await get_active_order(session, user)
        if not active:
            await message.answer("Нет активного заказа.", reply_markup=kb_main_menu())
            return
        now = utcnow()
        active.canceled = True
        user.updated_at = now
        logger.info(
            "Order cancelled",
            extra={"tg_id": user.tg_id, "user_id": user.id, "order_id": active.order_id},
        )
        await message.answer(RU.ORDER_CANCELED, reply_markup=kb_main_menu())


# ----------------------------------------------------------------------------
# Запуск бота
# ----------------------------------------------------------------------------

async def main() -> None:
    """Entry point for running the Telegram bot."""

    if not SETTINGS.BOT_TOKEN or ":" not in SETTINGS.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден или неверен. Укажите его в .env (BOT_TOKEN=...)")
    await init_models()
    await prepare_database()

    bot = Bot(SETTINGS.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware анти-флуда для всех сообщений (фактически ограничивает только кнопку «Клик»)
    dp.message.middleware(RateLimitMiddleware(get_user_click_limit))

    # Роутер
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started", extra={"event": "startup"})
    await dp.start_polling(bot)


if __name__ == "__main__":
    def _run_startup_checks() -> None:
        """Lightweight assertions to guard critical economic formulas."""

        assert finish_order_reward(100, 1.25) == base_reward_from_required(100, 1.25)
        assert finish_order_reward(100, 0.0) == base_reward_from_required(100, 1.0)


    _run_startup_checks()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped", extra={"event": "shutdown"})
