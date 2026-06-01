from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / "miniapp" / "src" / "i18n"


def _keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'"([^"]+)":', text))


def test_miniapp_locale_files_have_matching_keys() -> None:
    ru = _keys(I18N_DIR / "ru.ts")
    en = _keys(I18N_DIR / "en.ts")
    ky = _keys(I18N_DIR / "ky.ts")

    assert en - ru == set()
    assert ky - ru == set()
    assert ru - en == set()
    assert ru - ky == set()


def test_core_dashboard_i18n_keys_exist() -> None:
    keys = _keys(I18N_DIR / "ru.ts")
    required = {
        "owner.system_overview",
        "owner.tickets_by_status",
        "owner.close_stale",
        "manager.overview_active",
        "manager.search_chats",
        "customer.create_chat",
        "customer.request_mix",
        "ai.powered_by",
    }

    assert required <= keys
