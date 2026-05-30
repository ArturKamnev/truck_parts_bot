from __future__ import annotations

from app.services.keyboard_service import KeyboardService


def owner_panel_keyboard():
    return KeyboardService().get_owner_keyboard(None, None)


def model_id_by_index(index: int) -> str | None:
    from app.config import AVAILABLE_MODELS

    models = list(AVAILABLE_MODELS.keys())
    if 0 <= index < len(models):
        return models[index]
    return None
