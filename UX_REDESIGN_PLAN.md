# Designer Clicker Bot — UX Redesign Plan

## 1. Аудит текущего UX

### 1.1 Карта меню и клавиатур
| Клавиатура | Кнопки в rows | Доп. навигация через `_with_universal_nav` | Итого кнопок | Наблюдения |
| --- | --- | --- | --- | --- |
| `kb_main_menu` | 7 рядов: по 2 кнопки + одна одиночная (`/top`) | добавляет «◀️ Назад/❌ Отмена» и «🏠 Меню» | 16 уникальных | Топ-уровень перегружен и содержит Cancel. 【F:designer_clicker_bot.py†L293-L307】【F:designer_clicker_bot.py†L277-L286】 |
| `kb_shop_menu` | 2 ряда (⚡/🧰 и 📊) | те же нав-ряды | до 7 | Статистика в магазине, Cancel дублируется. 【F:designer_clicker_bot.py†L328-L334】 |
| `kb_profile_menu` | 1 ряд из 2–3 кнопок + отдельные строки | те же нав-ряды | до 8 | Cancel Order сочетается с глобальным Cancel. 【F:designer_clicker_bot.py†L336-L343】 |
| `kb_numeric_page` | первая строка 1–5, вторая — Prev/Next | нав-ряды | до 9 | Пагинация превращается в 3 строки навигации. 【F:designer_clicker_bot.py†L310-L322】 |
| `kb_confirm` | «✅ Подтвердить» + «❌ Отмена» | плюс ряд «◀️ Назад/❌ Отмена» + «🏠 Меню» | 5 кнопок (две «Отмена») | Подтверждения содержат Back и два Cancel. 【F:designer_clicker_bot.py†L323-L327】 |
| `kb_tutorial` / `kb_skill_choices` / `kb_quest_options` | 2–5 кнопок | нав-ряды | 4–8 | Даёт Cancel, хотя у шага обучения нет действия. 【F:designer_clicker_bot.py†L344-L360】 |

### 1.2 Ключевые UX-проблемы
1. **Перегруз главного меню** — 13 тематических кнопок + 3 навигационных нарушают правило 7±2 и Fitts' Law, растягивая действия. 【F:designer_clicker_bot.py†L293-L307】【F:designer_clicker_bot.py†L277-L286】
2. **Несогласованная навигация** — универсальный helper всегда добавляет и Back, и Cancel, даже на хабах и подтверждениях, порождая дубли и путаницу. 【F:designer_clicker_bot.py†L277-L286】
3. **Ручная маршрутизация Back/Cancel** — два почти одинаковых обработчика повторяют FSM-логику и часто завершают сцену вместо шага назад, что ломает ментальную модель. 【F:designer_clicker_bot.py†L3385-L3493】
4. **Потеря контекста** — сообщения часто представляют голый список без заголовка/прогресса (например, заказы показывают только числа, нет статуса «Стр. X/Y»). 【F:designer_clicker_bot.py†L2261-L2272】
5. **Избыточные подтверждения** — Cancel выводится и на действиях без потерь (tutorial, основное меню), что нарушает ритм и эмоциональный драйв. 【F:designer_clicker_bot.py†L344-L360】

### 1.3 Точки перегрузки
- **Заказы**: клавиатура даёт номера 1–5, нав Prev/Next, затем Back/Cancel/Menu — до 9 кнопок, при этом текст списка длинный и без разбивки. 【F:designer_clicker_bot.py†L310-L322】【F:designer_clicker_bot.py†L2261-L2272】
- **Профиль**: сообщение содержит плотный блок с множеством метрик, нет визуального разделения активных баффов/кампании/репутации. 【F:designer_clicker_bot.py†L2993-L3005】
- **Подтверждения**: две кнопки «Отмена» рядом (собственная + в навигации) и лишний «Назад» вносят когнитивный шум. 【F:designer_clicker_bot.py†L323-L327】

## 2. Новая структура меню
```
🏠 Главное меню (max 6 кнопок)
├── 🖱️ Клик
├── 💼 Работа
│   ├── 📋 Заказы
│   ├── 📜 Кампания
│   └── 😈 Квест
├── 🛒 Магазин
│   ├── ⚡ Бусты
│   └── 🧰 Экипировка
├── 👥 Команда
├── 🎒 Инвентарь
└── 👤 Профиль
    ├── 📊 Статистика
    ├── 🏆 Достижения
    ├── 🎯 Навыки
    ├── 🏢 Студия
    └── 🏆 Топ
```

**Правила навигации**
- Каждое подменю завершает сообщение строкой статуса («Страница 1/3», «Прогресс 40%»).
- Универсальная клавиатура содержит только допустимые элементы: «◀️ Назад» (если есть родитель) и «🏠 Меню». «❌ Отмена» — лишь на подтверждениях и длительных операциях.
- Пагинация: стрелки «◀️/▶️» отдельной строкой, номера — компактно, индикатор страниц в тексте.

## 3. Экранные макеты «до/после»

### 3.1 Главное меню
- **Было:** 13 тематических кнопок + Back/Cancel/Menu, сложно быстро найти нужный раздел. 【F:designer_clicker_bot.py†L293-L307】
- **Станет:**
  ```text
  🏠 Главное меню
  Выберите направление — и вперёд к репутации!
  🖱️ Клик | 💼 Работа
  🛒 Магазин | 👥 Команда
  🎒 Инвентарь | 👤 Профиль
  🧭 Кнопки: ◀️ Назад • 🏠 Меню
  ```

### 3.2 Заказы
- **Было:** «Заказы» выводят длинный список с цифрами и множеством кнопок. 【F:designer_clicker_bot.py†L2261-L2272】
- **Станет:**
  ```text
  📋 Доступные заказы — Стр. 1/3
  Уровень 5? Попробуйте свежие брифы!
  1️⃣ Визитка — 10 кликов
  2️⃣ Логотип — 15 кликов
  ◀️ Назад | ▶️ Далее
  🏠 Меню
  ```

### 3.3 Профиль
- **Было:** плотный блок без визуальных подсказок. 【F:designer_clicker_bot.py†L2993-L3005】
- **Станет:**
  ```text
  👤 Ваш профиль
  Уровень 7 • 320/450 XP • Баланс 1 540 ₽
  ⚡ Сила клика: 9 • Пассив: 120 ₽/мин
  📦 Активный заказ: Логотип (7/15)
  🔮 Баффы: Вирусный пост (5 мин)
  📜 Кампания: Глава 2 — 60%
  🏢 Репутация студии: 3 (+3% доход)
  ```

## 4. Рекомендации по коду

### 4.1 Единый helper навигации
```python
class UIHelper:
    @staticmethod
    def universal_nav(*, add_back: bool, add_cancel: bool = False, add_menu: bool = True) -> List[List[KeyboardButton]]:
        row: List[KeyboardButton] = []
        if add_back:
            row.append(KeyboardButton(text=RU.BTN_BACK))
        if add_cancel:
            row.append(KeyboardButton(text=RU.BTN_CANCEL))
        nav_rows = [row] if row else []
        if add_menu:
            nav_rows.append([KeyboardButton(text=RU.BTN_HOME)])
        return nav_rows

    @staticmethod
    def wrap(rows: List[List[KeyboardButton]], *, add_back: bool, add_cancel: bool = False, add_menu: bool = True) -> ReplyKeyboardMarkup:
        seen: Set[str] = set()
        deduped: List[List[KeyboardButton]] = []
        for row in rows + UIHelper.universal_nav(add_back=add_back, add_cancel=add_cancel, add_menu=add_menu):
            filtered = [btn for btn in row if btn.text not in seen]
            if filtered:
                seen.update(btn.text for btn in filtered)
                deduped.append(filtered)
        return ReplyKeyboardMarkup(keyboard=deduped, resize_keyboard=True)
```
- Хабы вызывают `UIHelper.wrap(rows, add_back=False)`.
- Подменю — `UIHelper.wrap(rows, add_back=True)`.
- Подтверждения — `UIHelper.wrap(rows, add_back=False, add_cancel=True)`.

### 4.2 Реструктуризация клавиатур
```diff
-def kb_main_menu() -> ReplyKeyboardMarkup:
-    rows = [
-        [KeyboardButton(text=RU.BTN_CLICK), KeyboardButton(text=RU.BTN_ORDERS)],
-        ...
-    ]
-    return _with_universal_nav(rows)
+def kb_main_menu() -> ReplyKeyboardMarkup:
+    rows = [
+        [KeyboardButton(text=RU.BTN_CLICK), KeyboardButton(text=RU.BTN_WORK)],
+        [KeyboardButton(text=RU.BTN_SHOP), KeyboardButton(text=RU.BTN_TEAM)],
+        [KeyboardButton(text=RU.BTN_WARDROBE), KeyboardButton(text=RU.BTN_PROFILE)],
+    ]
+    return UIHelper.wrap(rows, add_back=False)
```
(Где `RU.BTN_WORK = "💼 Работа"` — новая группа.)

Другие клавиатуры делятся на функции `kb_work_menu`, `kb_shop_menu`, `kb_profile_menu`, `kb_confirm_action` с передачей `add_cancel=True` только при необходимости.

### 4.3 Централизованный обработчик «Назад»
- В FSM-переходах добавить метаданные родительского экрана в `state.update_data(parent="work_root")`.
- Создать маппинг `PARENTS = {"orders": (OrdersState.browsing, kb_work_menu, RU.WORK_HEADER), ...}`.
- `handle_back` читает `parent` и переводит в нужное состояние, без дублирования цепочек `if current == …`.
- `cancel_any` остаётся только для подтверждений, где `add_cancel=True`.

### 4.4 Тексты
- Добавить в `RU` новые строки заголовков и коротких описаний (`WORK_HEADER`, `SHOP_PROMPT`, `PROFILE_HEADER`, `ORDERS_PAGE_FMT`, `PAGINATION_STATUS`).
- Переписать сообщения-хелперы с учётом ритма «заголовок → описание → действие/статус».

## 5. Патчи для ключевых обработчиков

### 5.1 Заказы
```diff
-    await message.answer(text, reply_markup=kb_numeric_page(show_prev, show_next))
+    status = RU.ORDERS_STATUS.format(page=page + 1, pages=pages)
+    await message.answer(
+        f"{RU.ORDERS_HEADER}\n{status}\n{body}",
+        reply_markup=kb_orders(page, pages, show_prev, show_next),
+    )
```
`kb_orders` возвращает номера 1–5 и отдельную строку стрелок через `UIHelper.wrap(..., add_back=True)`.

### 5.2 Подтверждения покупок
```diff
-def kb_confirm(confirm_text: str = RU.BTN_CONFIRM) -> ReplyKeyboardMarkup:
-    rows = [[KeyboardButton(text=confirm_text), KeyboardButton(text=RU.BTN_CANCEL)]]
-    return _with_universal_nav(rows)
+def kb_confirm(confirm_text: str = RU.BTN_CONFIRM) -> ReplyKeyboardMarkup:
+    rows = [[KeyboardButton(text=confirm_text), KeyboardButton(text=RU.BTN_CANCEL)]]
+    return UIHelper.wrap(rows, add_back=False, add_cancel=True)
```

### 5.3 Текст профиля
```diff
-        text = RU.PROFILE.format(...)
+        text = RU.PROFILE_HEADER.format(level=user.level, xp=user.xp, xp_need=xp_need)
+        text += "\n" + RU.PROFILE_STATS.format(cp=stats["cp"], pm=int(rate * 60))
+        text += "\n" + RU.PROFILE_ORDER.format(order=order_str)
+        text += "\n" + RU.PROFILE_BUFFS.format(buffs=buffs_text)
+        text += "\n" + RU.PROFILE_CAMPAIGN.format(campaign=campaign_text)
+        text += "\n" + RU.PROFILE_PRESTIGE.format(rep=prestige.reputation)
```

### 5.4 Обновлённые клавиатуры
```python
def kb_work_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=RU.BTN_ORDERS), KeyboardButton(text=RU.BTN_CAMPAIGN)],
        [KeyboardButton(text=RU.BTN_QUEST)],
    ]
    return UIHelper.wrap(rows, add_back=True)
```
Аналогично `kb_shop_menu`, `kb_profile_menu`.

## 6. Таблица «до / после»
| Экран | Было | Стало | Изменение UX |
| --- | --- | --- | --- |
| Главное меню | 13 тематических кнопок + Cancel/Menu | 6 кнопок без Cancel | Снижение когнитивной нагрузки, быстрее выбор |
| Заказы | 8–10 кнопок (номера, Prev/Next, Back/Cancel/Menu) | 6 кнопок (номера, стрелки, Меню) | Чёткая навигация, меньше ошибок |
| Профиль | Сплошной текстовый блок | Структурированные строки с заголовками | Улучшена читаемость и удержание информации |
| Подтверждения | «Отмена» дублируется, есть «Назад» | «Подтвердить/Отмена» + «Меню» | Предсказуемый исход, нет лишних выборов |

## 7. План внедрения
1. Добавить `UIHelper` и заменить вызовы `_with_universal_nav`.
2. Пересобрать набор `RU`-строк и основные сообщения согласно новой структуре.
3. Переписать клавиатуры на модульные (`kb_main_menu`, `kb_work_menu`, `kb_orders`, …).
4. Обновить обработчики Back/Cancel, используя хранилище родителя в `FSMContext`.
5. Протестировать сценарии: переходы между меню, подтверждения покупок, пагинация заказов.
6. Провести UX smoke-test с 5–10 кликами и завершением заказа, убедиться в отсутствии двойных «Отмена».
