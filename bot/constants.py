"""Core constants and localized strings."""
from __future__ import annotations

from dataclasses import dataclass


EQUIPMENT_SLOTS = ["laptop", "phone", "tablet", "monitor", "chair"]
PAGE_SIZE = 5


@dataclass(frozen=True, slots=True)
class LocaleRU:
    """Russian localized strings used by the bot."""

    BTN_CLICK: str = "Клик"
    BTN_ORDERS: str = "Заказы"
    BTN_SHOP: str = "Магазин"
    BTN_TEAM: str = "Команда"
    BTN_WARDROBE: str = "Гардероб"
    BTN_PROFILE: str = "Профиль"
    BTN_MENU: str = "В меню"
    BTN_PREV: str = "Назад страница"
    BTN_NEXT: str = "Вперёд страница"
    BTN_TAKE: str = "Взять заказ"
    BTN_CANCEL: str = "Отмена"
    BTN_CONFIRM: str = "Подтвердить"
    BTN_EQUIP: str = "Экипировать"
    BTN_BUY: str = "Купить"
    BTN_UPGRADE: str = "Повысить"
    BTN_BOOSTS: str = "Бусты"
    BTN_EQUIPMENT: str = "Экипировка"
    BTN_DAILY: str = "Ежедневный бонус"
    BTN_CANCEL_ORDER: str = "Отменить заказ"

    BOT_STARTED: str = "Бот запущен."
    WELCOME: str = "Добро пожаловать в «Дизайнер»! Вам начислено 200 ₽. ыберите действие:"
    MENU_HINT: str = "Главное меню:"
    TOO_FAST: str = "Слишком быстро! Лимит кликов достигнут."
    NO_ACTIVE_ORDER: str = "У вас нет активного заказа. Откройте раздел «Заказы»."
    CLICK_PROGRESS: str = "Прогресс: {cur}/{req} кликов ({pct}%)."
    ORDER_TAKEN: str = "Вы взяли заказ: {title}. Удачи!"
    ORDER_ALREADY: str = "У вас уже есть активный заказ."
    ORDER_DONE: str = "Заказ завершён! Награда: {rub} ₽, XP: {xp}."
    ORDER_CANCELED: str = "Заказ отменён. Прогресс сброшен."
    INSUFFICIENT_FUNDS: str = "Недостаточно средств."
    PURCHASE_OK: str = "Покупка успешна."
    UPGRADE_OK: str = "Повышение выполнено."
    EQUIP_OK: str = "Экипировано."
    EQUIP_NOITEM: str = "Сначала купите предмет."
    DAILY_OK: str = "Начислен ежедневный бонус: {rub} ₽."
    DAILY_WAIT: str = "Бонус уже получен. Загляните позже."
    PROFILE: str = (
        "Профиль\n"
        "Уровень: {lvl}\nXP: {xp}/{xp_need}\n"
        "Баланс: {rub} ₽\n"
        "CP: {cp}\n"
        "Пассивный доход: {pm}/мин\n"
        "Текущий заказ: {order}"
    )
    TEAM_HEADER: str = "Команда (доход/мин, уровень, цена повышения):"
    SHOP_HEADER: str = "Магазин — выберите раздел:"
    WARDROBE_HEADER: str = "Гардероб — слоты и инвентарь:"
    ORDERS_HEADER: str = "Доступные заказы (номер для выбора):"

    CURRENCY: str = "₽"


RU = LocaleRU()
