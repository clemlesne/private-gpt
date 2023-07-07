from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class MessageRole(str, Enum):
    ASSISTANT = "assistant"
    SYSTEM = "system"
    USER = "user"


class MessageModel(BaseModel):
    content: str
    created_at: datetime
    id: UUID
    role: MessageRole
    secret: bool
    token: Optional[UUID] = None


class StoredMessageModel(MessageModel):
    conversation_id: UUID


class IndexMessageModel(BaseModel):
    """
    Storing the message in a separate collection allows us to query for messages. It does not contain the message content, but only the metadata required to query for the message.

    The absence of content and created_at is intentional. We don't want to store PII in the index. As this, we are not forced to apply a TTL to the index nor secure too much the DB.
    """
    conversation_id: UUID
    id: UUID
    user_id: UUID
