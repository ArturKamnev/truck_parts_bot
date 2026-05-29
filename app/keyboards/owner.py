from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.config import AVAILABLE_MODELS, Settings
from app.utils.enums import BroadcastButtonSelection


def owner_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Выбрать модель ИИ", callback_data="owner:models")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="owner:stats")],
            [InlineKeyboardButton(text="📨 Разослать", callback_data="broadcast:start")],
            [InlineKeyboardButton(text="📋 История рассылок", callback_data="broadcast:history")],
            [
                InlineKeyboardButton(
                    text="📂 Открытые обращения", callback_data="owner:open_tickets"
                )
            ],
        ]
    )


def model_selection_keyboard(active_model: str) -> InlineKeyboardMarkup:
    rows = []
    for index, (model_id, label) in enumerate(AVAILABLE_MODELS.items()):
        prefix = "✅ " if model_id == active_model else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{label}",
                    callback_data=f"owner:model:{index}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_id_by_index(index: int) -> str | None:
    models = list(AVAILABLE_MODELS.keys())
    if 0 <= index < len(models):
        return models[index]
    return None


def owner_ticket_keyboard(ticket_id: int, *, can_claim: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"💬 Открыть #{ticket_id}",
                callback_data=f"ticket:open:{ticket_id}",
            )
        ]
    ]
    if can_claim:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Взять в работу", callback_data=f"ticket:claim:{ticket_id}"
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔒 Закрыть вопрос",
                callback_data=f"ticket:close:{ticket_id}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner:open_tickets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        input_field_placeholder="Сообщение для рассылки",
    )


def broadcast_button_selection_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Без кнопок",
                callback_data=f"broadcast:buttons:{BroadcastButtonSelection.NONE.value}",
            )
        ]
    ]
    if settings.instagram_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Instagram",
                    callback_data=f"broadcast:buttons:{BroadcastButtonSelection.INSTAGRAM.value}",
                )
            ]
        )
    if settings.official_site_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Официальный сайт",
                    callback_data=f"broadcast:buttons:{BroadcastButtonSelection.SITE.value}",
                )
            ]
        )
    if settings.instagram_url and settings.official_site_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Instagram + сайт",
                    callback_data=f"broadcast:buttons:{BroadcastButtonSelection.BOTH.value}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧪 Отправить тест мне", callback_data="broadcast:test")],
            [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:send_all")],
            [InlineKeyboardButton(text="✏️ Создать заново", callback_data="broadcast:restart")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")],
        ]
    )


def broadcast_confirm_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтверждаю отправку",
                    callback_data=f"broadcast:confirm:{broadcast_id}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")],
        ]
    )


def broadcast_report_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть отчёт", callback_data=f"broadcast:report:{broadcast_id}"
                )
            ]
        ]
    )
