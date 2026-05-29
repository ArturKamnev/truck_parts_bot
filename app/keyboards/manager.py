from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

MANAGER_NEW_TICKETS = "📥 Новые обращения"
MANAGER_ACTIVE_CHATS = "💬 Мои активные диалоги"
MANAGER_STATS = "📊 Моя статистика"
MANAGER_NOTIFICATIONS = "🔔 Уведомления"


def manager_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MANAGER_NEW_TICKETS), KeyboardButton(text=MANAGER_ACTIVE_CHATS)],
            [KeyboardButton(text=MANAGER_STATS), KeyboardButton(text=MANAGER_NOTIFICATIONS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def ticket_claim_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Взять в работу", callback_data=f"ticket:claim:{ticket_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁 История", callback_data=f"ticket:history:{ticket_id}"
                )
            ]
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
            ]
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
