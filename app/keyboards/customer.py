from __future__ import annotations

from app.services.keyboard_service import KeyboardService
from app.utils.enums import CustomerMode


def customer_keyboard(*, broadcasts_enabled: bool = True):
    return KeyboardService().get_customer_keyboard(CustomerMode.AI_CHAT.value, broadcasts_enabled)
