from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import AVAILABLE_MODELS, Settings
from app.utils.enums import BroadcastButtonSelection


def customer_cancel_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, отменить", callback_data="customer:cancel:yes"),
                InlineKeyboardButton(text="Нет", callback_data="customer:cancel:no"),
            ]
        ]
    )


def ticket_claim_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Взять в работу", callback_data=f"ticket:claim:{ticket_id}"
                )
            ],
            [InlineKeyboardButton(text="👁 История", callback_data=f"ticket:history:{ticket_id}")],
        ]
    )


def ticket_chat_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔒 Закрыть вопрос", callback_data=f"ticket:close:{ticket_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏸ Выйти из режима ответа", callback_data="operator:exit_reply"
                )
            ],
            [InlineKeyboardButton(text="↩️ Мои диалоги", callback_data="manager:active")],
        ]
    )


def active_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть диалог",
                    callback_data=f"ticket:open:{ticket_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Закрыть вопрос",
                    callback_data=f"ticket:close:{ticket_id}",
                )
            ],
        ]
    )


def notification_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if enabled:
        rows.append(
            [InlineKeyboardButton(text="Выключить уведомления", callback_data="manager:notify:off")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text="Включить уведомления", callback_data="manager:notify:on")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
