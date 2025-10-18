"""Economic and progression related utilities."""
from __future__ import annotations

from math import floor


def xp_to_level(level: int) -> int:
    """Return XP required to reach ``level``."""

    return 100 * level * level


def upgrade_cost(base_cost: int, growth: float, next_level: int) -> int:
    """Return the upgrade cost for ``next_level`` with geometric growth."""

    return round(base_cost * (growth ** (next_level - 1)))


def required_clicks(base_clicks: int, level: int) -> int:
    """Calculate required clicks for an order for a player level."""

    return int(round(base_clicks * (1 + 0.15 * floor(level / 5))))


def base_reward_from_required(required: int, reward_multiplier: float = 1.0) -> int:
    """Return base reward for finishing an order."""

    return int(round(required * 0.6 * reward_multiplier))


def snapshot_required_clicks(base_clicks: int, user_level: int, reduction_pct: float) -> int:
    """Snapshot required clicks with equipment reductions applied."""

    base_required = required_clicks(base_clicks, user_level)
    reduced = int(round(base_required * (1 - reduction_pct)))
    return max(1, reduced)


def finish_order_reward(required_clicks_snapshot: int, reward_multiplier: float) -> int:
    """Return reward for finishing an order using a snapshot of requirements."""

    return base_reward_from_required(required_clicks_snapshot, reward_multiplier)


def team_income_per_min(base_per_min: float, level: int) -> float:
    """Return income per minute for a hired team member."""

    if level <= 0:
        return 0.0
    return base_per_min * (1 + 0.25 * (level - 1))
