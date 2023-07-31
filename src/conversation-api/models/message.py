from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class MessageRole(str, Enum):
    ASSISTANT = "assistant"
    USER = "user"


class MessageModel(BaseModel):
    actions: Optional[list[str]] = None  # Optional for backward compatibility
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extra: Optional[Dict[str, Any]] = Field(
        default_factory=dict
    )  # Optional for backward compatibility
    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    secret: bool
    token: Optional[UUID] = Field(
        default_factory=uuid4
    )  # Optional for backward compatibility


class StoredMessageModel(MessageModel):
    conversation_id: UUID  # Partition key


class IndexMessageModel(BaseModel):
    """
    Storing the message in a separate collection allows us to query for messages. It does not contain the message content, but only the metadata required to query for the message.

    The absence of content and created_at is intentional. We don't want to store PII in the index. As this, we are not forced to apply a TTL to the index nor secure too much the DB.
    """

    conversation_id: UUID
    id: UUID


class StreamMessageModel(BaseModel):
    action: Optional[str] = None
    content: Optional[str] = None
