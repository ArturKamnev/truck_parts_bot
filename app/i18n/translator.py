from __future__ import annotations

from app.i18n.ru import translations as ru_translations
from app.i18n.en import translations as en_translations
from app.i18n.ky import translations as ky_translations

LOCALES = {
    "ru": ru_translations,
    "en": en_translations,
    "ky": ky_translations,
}

DEFAULT_LOCALE = "ru"


def translate(key: str, locale: str | None = None, **kwargs) -> str:
    """
    Translates a key into the given locale, falling back to 'ru'.
    Supports string formatting via kwargs.
    """
    lang = (locale or DEFAULT_LOCALE).lower()
    if lang not in LOCALES:
        if lang.startswith("ru"):
            lang = "ru"
        elif lang.startswith("en"):
            lang = "en"
        elif lang.startswith("ky") or lang.startswith("kg"):
            lang = "ky"
        else:
            lang = DEFAULT_LOCALE

    translations_dict = LOCALES.get(lang, ru_translations)
    text = translations_dict.get(key, ru_translations.get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_button_text_set(key: str) -> list[str]:
    """
    Returns a list of all translated texts for a specific key (button) across all supported locales.
    Used for routing matching in aiogram filters.
    """
    results = []
    for loc in LOCALES:
        val = LOCALES[loc].get(key, ru_translations.get(key, key))
        results.append(val)
    return list(set(results))


def get_button_key_by_value(value: str) -> str | None:
    """
    Finds the key corresponding to a translated button value.
    """
    for locale_dict in LOCALES.values():
        for k, v in locale_dict.items():
            if v == value:
                return k
    return None


def detect_language_code(tg_code: str | None) -> str:
    """
    Maps incoming Telegram or Mini App WebApp language codes to ru, en, or ky.
    """
    if not tg_code:
        return "ru"
    tg_code = tg_code.strip().lower()
    if tg_code.startswith("ru"):
        return "ru"
    if tg_code.startswith("en"):
        return "en"
    if tg_code.startswith("ky") or tg_code.startswith("kg"):
        return "ky"
    return "ru"
