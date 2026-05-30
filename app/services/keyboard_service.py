from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from app.config import get_settings

from app.keyboards.constants import (
    CUSTOMER_ASK_AI,
    CUSTOMER_BROADCASTS_OFF,
    CUSTOMER_BROADCASTS_ON,
    CUSTOMER_CANCEL,
    CUSTOMER_CANCEL_REQUEST,
    CUSTOMER_CLOSE_CHAT,
    CUSTOMER_CONTACT_MANAGER,
    MANAGER_ACTIVE_CHATS,
    MANAGER_CLOSE_TICKET,
    MANAGER_EXIT_REPLY,
    MANAGER_MY_DIALOGS,
    MANAGER_NEW_TICKETS,
    MANAGER_NOTIFICATIONS_OFF,
    MANAGER_NOTIFICATIONS_ON,
    MANAGER_STATS,
    OWNER_BACK,
    OWNER_BROADCAST,
    OWNER_BROADCAST_HISTORY,
    OWNER_CANCEL,
    OWNER_CHOOSE_MODEL,
    OWNER_STATS,
    OWNER_TICKETS,
    OWNER_MANAGERS,
    OWNER_PROMOTE_MANAGER,
    OWNER_MANAGER_STATS,
)
from app.utils.enums import CustomerMode, OwnerWorkflowState


class KeyboardService:
    def get_customer_keyboard(
        self, mode: str | CustomerMode, broadcasts_enabled: bool
    ) -> ReplyKeyboardMarkup:
        if mode == CustomerMode.REQUESTING_MANAGER.value:
            keyboard = [[KeyboardButton(text=CUSTOMER_CANCEL)]]
        elif mode == CustomerMode.WAITING_MANAGER.value:
            keyboard = [[KeyboardButton(text=CUSTOMER_CANCEL_REQUEST)]]
        elif mode == CustomerMode.MANAGER_CHAT.value:
            keyboard = [[KeyboardButton(text=CUSTOMER_CLOSE_CHAT)]]
        else:
            broadcast_btn = (
                CUSTOMER_BROADCASTS_ON if broadcasts_enabled else CUSTOMER_BROADCASTS_OFF
            )
            keyboard = []
            settings = get_settings()
            if settings.miniapp_url:
                keyboard.append([
                    KeyboardButton(
                        text="💬 Открыть Mini App",
                        web_app=WebAppInfo(url=settings.miniapp_url)
                    )
                ])
            keyboard.extend([
                [
                    KeyboardButton(text=CUSTOMER_ASK_AI),
                    KeyboardButton(text=CUSTOMER_CONTACT_MANAGER),
                ],
                [KeyboardButton(text=broadcast_btn)],
            ])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def get_manager_keyboard(
        self, selected_ticket_id: int | None, notifications_enabled: bool
    ) -> ReplyKeyboardMarkup:
        if selected_ticket_id is not None:
            keyboard = [
                [KeyboardButton(text=MANAGER_CLOSE_TICKET)],
                [KeyboardButton(text=MANAGER_EXIT_REPLY)],
                [KeyboardButton(text=MANAGER_MY_DIALOGS)],
            ]
        else:
            notif_btn = (
                MANAGER_NOTIFICATIONS_ON if notifications_enabled else MANAGER_NOTIFICATIONS_OFF
            )
            keyboard = [
                [
                    KeyboardButton(text=MANAGER_NEW_TICKETS),
                    KeyboardButton(text=MANAGER_ACTIVE_CHATS),
                ],
                [KeyboardButton(text=MANAGER_STATS), KeyboardButton(text=notif_btn)],
            ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def get_owner_keyboard(
        self, workflow_state: str | None, selected_ticket_id: int | None
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
            keyboard = [[KeyboardButton(text=OWNER_CANCEL), KeyboardButton(text=OWNER_BACK)]]
        else:
            keyboard = [
                [KeyboardButton(text=OWNER_CHOOSE_MODEL)],
                [KeyboardButton(text=OWNER_STATS), KeyboardButton(text=OWNER_TICKETS)],
                [
                    KeyboardButton(text=OWNER_BROADCAST),
                    KeyboardButton(text=OWNER_BROADCAST_HISTORY),
                ],
                [
                    KeyboardButton(text=OWNER_MANAGERS),
                    KeyboardButton(text=OWNER_PROMOTE_MANAGER),
                ],
                [KeyboardButton(text=OWNER_MANAGER_STATS)],
            ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
