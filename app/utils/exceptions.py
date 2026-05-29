from __future__ import annotations


class BotError(Exception):
    """Base domain exception."""


class AuthorizationError(BotError):
    """Raised when a Telegram user is not allowed to perform an action."""


class TicketStateError(BotError):
    """Raised when a ticket action is invalid for its current state."""


class DuplicateActiveTicketError(BotError):
    """Raised when a customer already has an active ticket."""


class UnsupportedRelayContentError(BotError):
    """Raised when a Telegram message cannot be safely relayed."""


class AIServiceError(BotError):
    """Raised for user-safe AI service failures."""
