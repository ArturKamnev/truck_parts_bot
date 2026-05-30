from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import AVAILABLE_MODELS, Settings
from app.utils.enums import BroadcastButtonSelection
from app.i18n.translator import translate


def language_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:set:ru"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:set:en"),
                InlineKeyboardButton(text="🇰🇬 Кыргызча", callback_data="lang:set:ky"),
            ]
        ]
    )


def customer_cancel_confirmation_keyboard(locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=translate("inline.cancel_yes", locale), callback_data="customer:cancel:yes"),
                InlineKeyboardButton(text=translate("inline.cancel_no", locale), callback_data="customer:cancel:no"),
            ]
        ]
    )


def ticket_claim_keyboard(ticket_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.claim_ticket", locale), callback_data=f"ticket:claim:{ticket_id}"
                )
            ],
            [InlineKeyboardButton(text=translate("inline.history", locale), callback_data=f"ticket:history:{ticket_id}")],
        ]
    )


def ticket_chat_keyboard(ticket_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.close_question", locale), callback_data=f"ticket:close:{ticket_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=translate("inline.exit_reply", locale), callback_data="operator:exit_reply"
                )
            ],
            [InlineKeyboardButton(text=translate("inline.my_dialogs", locale), callback_data="manager:active")],
        ]
    )


def active_ticket_keyboard(ticket_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.open_dialog", locale),
                    callback_data=f"ticket:open:{ticket_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=translate("inline.close_question", locale),
                    callback_data=f"ticket:close:{ticket_id}",
                )
            ],
        ]
    )


def notification_keyboard(enabled: bool, locale: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if enabled:
        rows.append(
            [InlineKeyboardButton(text=translate("inline.turn_off_notify", locale), callback_data="manager:notify:off")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text=translate("inline.turn_on_notify", locale), callback_data="manager:notify:on")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_selection_keyboard(active_model: str, locale: str | None = None) -> InlineKeyboardMarkup:
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
    rows.append([InlineKeyboardButton(text=translate("inline.go_back", locale), callback_data="owner:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def owner_ticket_keyboard(ticket_id: int, *, can_claim: bool, locale: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=translate("inline.open_ticket_id", locale, id=ticket_id),
                callback_data=f"ticket:open:{ticket_id}",
            )
        ]
    ]
    if can_claim:
        rows.append(
            [
                InlineKeyboardButton(
                    text=translate("inline.claim_ticket", locale), callback_data=f"ticket:claim:{ticket_id}"
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=translate("inline.close_question", locale),
                callback_data=f"ticket:close:{ticket_id}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=translate("inline.go_back", locale), callback_data="owner:open_tickets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_button_selection_keyboard(settings: Settings, locale: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=translate("inline.no_buttons", locale),
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
                    text=translate("inline.official_site", locale),
                    callback_data=f"broadcast:buttons:{BroadcastButtonSelection.SITE.value}",
                )
            ]
        )
    if settings.instagram_url and settings.official_site_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text=translate("inline.both_buttons", locale),
                    callback_data=f"broadcast:buttons:{BroadcastButtonSelection.BOTH.value}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=translate("common.cancel", locale), callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_preview_keyboard(locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("inline.send_test_me", locale), callback_data="broadcast:test")],
            [InlineKeyboardButton(text=translate("inline.send_all", locale), callback_data="broadcast:send_all")],
            [InlineKeyboardButton(text=translate("inline.create_new", locale), callback_data="broadcast:restart")],
            [InlineKeyboardButton(text=translate("common.cancel", locale), callback_data="broadcast:cancel")],
        ]
    )


def broadcast_confirm_keyboard(broadcast_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.confirm_send", locale),
                    callback_data=f"broadcast:confirm:{broadcast_id}",
                )
            ],
            [InlineKeyboardButton(text=translate("common.cancel", locale), callback_data="broadcast:cancel")],
        ]
    )


def broadcast_report_keyboard(broadcast_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.open_report", locale), callback_data=f"broadcast:report:{broadcast_id}"
                )
            ]
        ]
    )


def owner_manager_keyboard(telegram_user_id: int, is_active: bool, locale: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if is_active:
        rows.append([
            InlineKeyboardButton(
                text=translate("inline.disable_manager", locale),
                callback_data=f"owner:manager:disable_prompt:{telegram_user_id}"
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text=translate("inline.enable_manager", locale),
                callback_data=f"owner:manager:enable:{telegram_user_id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def owner_manager_disable_confirm_keyboard(telegram_user_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.disable_manager_confirm", locale),
                    callback_data=f"owner:manager:disable_confirm:{telegram_user_id}"
                ),
                InlineKeyboardButton(
                    text=translate("common.cancel", locale),
                    callback_data="owner:managers_list"
                )
            ]
        ]
    )


def owner_promote_users_keyboard(users: list[tuple[int, str]], locale: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    for user_id, display_name in users:
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {display_name}",
                callback_data=f"owner:promote_user:{user_id}"
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=translate("common.cancel", locale),
            callback_data="owner:panel"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def owner_promote_unknown_confirm_keyboard(telegram_user_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate("inline.promote_confirm", locale),
                    callback_data=f"owner:promote_unknown_confirm:{telegram_user_id}"
                ),
                InlineKeyboardButton(
                    text=translate("common.cancel", locale),
                    callback_data="owner:panel"
                )
            ]
        ]
    )
