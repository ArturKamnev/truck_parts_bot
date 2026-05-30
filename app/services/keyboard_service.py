from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from app.config import get_settings
from app.utils.enums import CustomerMode, OwnerWorkflowState
from app.i18n.translator import translate


class KeyboardService:
    def get_customer_keyboard(
        self, mode: str | CustomerMode, broadcasts_enabled: bool, locale: str | None = None
    ) -> ReplyKeyboardMarkup:
        if mode == CustomerMode.REQUESTING_MANAGER.value:
            keyboard = [[KeyboardButton(text=translate("customer.cancel", locale))]]
        elif mode == CustomerMode.WAITING_MANAGER.value:
            keyboard = [[KeyboardButton(text=translate("customer.cancel_request", locale))]]
        elif mode == CustomerMode.MANAGER_CHAT.value:
            keyboard = [[KeyboardButton(text=translate("customer.close_chat", locale))]]
        else:
            broadcast_key = "customer.broadcasts_on" if broadcasts_enabled else "customer.broadcasts_off"
            keyboard = []
            settings = get_settings()
            if settings.miniapp_url:
                keyboard.append([
                    KeyboardButton(
                        text=translate("bot.open_miniapp", locale),
                        web_app=WebAppInfo(url=settings.miniapp_url)
                    )
                ])
            keyboard.extend([
                [
                    KeyboardButton(text=translate("customer.ask_ai", locale)),
                    KeyboardButton(text=translate("customer.contact_manager", locale)),
                ],
                [
                    KeyboardButton(text=translate(broadcast_key, locale)),
                    KeyboardButton(text=translate("bot.language_btn", locale)),
                ],
            ])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def get_manager_keyboard(
        self, selected_ticket_id: int | None, notifications_enabled: bool, locale: str | None = None
    ) -> ReplyKeyboardMarkup:
        if selected_ticket_id is not None:
            keyboard = [
                [KeyboardButton(text=translate("manager.close_ticket", locale))],
                [KeyboardButton(text=translate("manager.exit_reply", locale))],
                [KeyboardButton(text=translate("manager.my_dialogs", locale))],
            ]
        else:
            notif_key = "manager.notifications_on" if notifications_enabled else "manager.notifications_off"
            keyboard = [
                [
                    KeyboardButton(text=translate("manager.new_tickets", locale)),
                    KeyboardButton(text=translate("manager.active_chats", locale)),
                ],
                [
                    KeyboardButton(text=translate("manager.stats", locale)),
                    KeyboardButton(text=translate(notif_key, locale)),
                ],
                [KeyboardButton(text=translate("bot.language_btn", locale))],
            ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def get_owner_keyboard(
        self, workflow_state: str | None, selected_ticket_id: int | None, locale: str | None = None
    ) -> ReplyKeyboardMarkup:
        is_temporary_mode = (
            workflow_state
            in {
                OwnerWorkflowState.CREATING_BROADCAST_CONTENT.value,
                OwnerWorkflowState.CHOOSING_BROADCAST_BUTTONS.value,
                OwnerWorkflowState.PREVIEWING_BROADCAST.value,
                OwnerWorkflowState.CONFIRMING_BROADCAST.value,
                OwnerWorkflowState.AWAITING_MANAGER_ID.value,
                "MODEL_SELECTION",
            }
            or selected_ticket_id is not None
        )
        if is_temporary_mode:
            keyboard = [[
                KeyboardButton(text=translate("owner.cancel", locale)),
                KeyboardButton(text=translate("owner.back", locale))
            ]]
        else:
            keyboard = [
                [KeyboardButton(text=translate("owner.choose_model", locale))],
                [
                    KeyboardButton(text=translate("owner.stats", locale)),
                    KeyboardButton(text=translate("owner.tickets", locale))
                ],
                [
                    KeyboardButton(text=translate("owner.broadcast", locale)),
                    KeyboardButton(text=translate("owner.broadcast_history", locale)),
                ],
                [
                    KeyboardButton(text=translate("owner.managers", locale)),
                    KeyboardButton(text=translate("owner.promote_manager", locale)),
                ],
                [
                    KeyboardButton(text=translate("owner.manager_stats", locale)),
                    KeyboardButton(text=translate("bot.language_btn", locale)),
                ],
            ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
