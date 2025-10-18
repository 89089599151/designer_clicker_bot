"""Declarative SQLAlchemy models."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    balance: Mapped[int] = mapped_column(Integer, default=200)
    cp_base: Mapped[int] = mapped_column(Integer, default=1)
    reward_mul: Mapped[float] = mapped_column(Float, default=0.0)
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
    reward_snapshot_mul: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped["User"] = relationship(back_populates="orders")
    order: Mapped["Order"] = relationship()


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
    level: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "member_id", name="uq_user_team"),)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slot: Mapped[Literal["laptop", "phone", "tablet", "monitor", "chair"]] = mapped_column(String(20))
    tier: Mapped[int] = mapped_column(Integer)
    bonus_type: Mapped[
        Literal["cp_pct", "passive_pct", "req_clicks_pct", "reward_pct", "ratelimit_plus"]
    ] = mapped_column(String(30))
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
    meta: Mapped[Optional[Dict[str, object]]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_economy_user_created", "user_id", "created_at"),)
