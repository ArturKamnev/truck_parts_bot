from __future__ import annotations

from app.services.keyboard_service import KeyboardService


def manager_keyboard():
    return KeyboardService().get_manager_keyboard(None, True)
