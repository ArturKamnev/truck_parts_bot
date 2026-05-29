from __future__ import annotations

from enum import StrEnum


class CustomerMode(StrEnum):
    AI_CHAT = "AI_CHAT"
    REQUESTING_MANAGER = "REQUESTING_MANAGER"
    WAITING_MANAGER = "WAITING_MANAGER"
    MANAGER_CHAT = "MANAGER_CHAT"


class OwnerWorkflowState(StrEnum):
    CREATING_BROADCAST_CONTENT = "CREATING_BROADCAST_CONTENT"
    CHOOSING_BROADCAST_BUTTONS = "CHOOSING_BROADCAST_BUTTONS"
    PREVIEWING_BROADCAST = "PREVIEWING_BROADCAST"
    CONFIRMING_BROADCAST = "CONFIRMING_BROADCAST"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    CLOSED = "CLOSED"
    CANCELLED_BY_CUSTOMER = "CANCELLED_BY_CUSTOMER"


class AIMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class TicketMessageSenderType(StrEnum):
    CUSTOMER = "customer"
    MANAGER = "manager"
    OWNER = "owner"
    SYSTEM = "system"


class TicketMessageContentType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    ANIMATION = "animation"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"


class TicketMessageDeliveryStatus(StrEnum):
    STORED = "stored"
    PENDING_MEDIA_GROUP = "pending_media_group"
    DELIVERED = "delivered"
    FAILED = "failed"


class BroadcastStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENDING = "SENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class BroadcastDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class BroadcastButtonSelection(StrEnum):
    NONE = "none"
    INSTAGRAM = "instagram"
    SITE = "site"
    BOTH = "both"
