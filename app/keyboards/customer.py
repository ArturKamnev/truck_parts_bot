from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

ASK_AI = "🤖 Задать вопрос"
CONTACT_MANAGER = "👨‍💼 Связаться с менеджером"
CANCEL_MANAGER_REQUEST = "❌ Отмена"
CANCEL_ACTIVE_REQUEST = "❌ Отменить обращение"
CLOSE_MANAGER_CHAT = "✅ Завершить диалог"
BROADCASTS_ENABLED = "🔔 Рассылки: включены"
BROADCASTS_DISABLED = "🔕 Рассылки: выключены"


def customer_keyboard(*, broadcasts_enabled: bool = True) -> ReplyKeyboardMarkup:
    broadcast_text = BROADCASTS_ENABLED if broadcasts_enabled else BROADCASTS_DISABLED
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ASK_AI), KeyboardButton(text=CONTACT_MANAGER)],
            [KeyboardButton(text=broadcast_text)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите вопрос",
    )


def requesting_manager_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_MANAGER_REQUEST)]],
        resize_keyboard=True,
        input_field_placeholder="Опишите вопрос или приложите файл",
    )


def waiting_manager_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_ACTIVE_REQUEST)]],
        resize_keyboard=True,
        input_field_placeholder="Можно отправить дополнительные сообщения",
    )


def manager_chat_customer_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CLOSE_MANAGER_CHAT)]],
        resize_keyboard=True,
        input_field_placeholder="Сообщение менеджеру",
    )


def customer_cancel_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, отменить", callback_data="customer:cancel:yes"),
                InlineKeyboardButton(text="Нет", callback_data="customer:cancel:no"),
            ]
        ]
    )
