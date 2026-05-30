from __future__ import annotations

from types import SimpleNamespace

from app.services.telegram_stream_renderer import (
    TelegramPartialResponseRenderer,
    TelegramStreamRendererConfig,
)


class EditableMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.edits: list[dict] = []
        self.message_id = 1

    async def edit_text(self, text: str, **kwargs) -> None:
        self.text = text
        self.edits.append({"text": text, **kwargs})


class FakeMessage:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(id=500)
        self.answers: list[dict] = []
        self.editable = EditableMessage("")

    async def answer(self, text: str, **kwargs):
        self.answers.append({"text": text, **kwargs})
        self.editable = EditableMessage(text)
        return self.editable


class FakeBot:
    token = "123:test"

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)
        return EditableMessage(kwargs["text"])


async def test_renderer_throttles_updates_and_finalizes_complete_answer() -> None:
    renderer = TelegramPartialResponseRenderer(
        TelegramStreamRendererConfig(
            update_interval_seconds=100.0,
            min_chars=10,
            use_telegram_draft=False,
        )
    )
    message = FakeMessage()
    bot = FakeBot()

    await renderer.start(message, bot)
    await renderer.render_partial(bot, 500, "short")
    await renderer.render_partial(bot, 500, "long enough text")
    await renderer.finalize(bot, 500, "complete answer")

    assert message.answers[0]["text"] == "💭 Думаю..."
    assert [edit["text"] for edit in message.editable.edits] == [
        "long enough text",
        "complete answer",
    ]


async def test_renderer_falls_back_when_send_message_draft_is_unavailable(monkeypatch) -> None:
    renderer = TelegramPartialResponseRenderer(
        TelegramStreamRendererConfig(
            update_interval_seconds=0.1,
            min_chars=1,
            use_telegram_draft=True,
        )
    )

    async def draft_unavailable(**kwargs) -> bool:
        return False

    monkeypatch.setattr(renderer, "_send_message_draft", draft_unavailable)
    message = FakeMessage()

    await renderer.start(message, FakeBot())

    assert message.answers[0]["text"] == "💭 Думаю..."
