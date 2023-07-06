from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
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


class IndexMessageModel(BaseModel):
    conversation_id: UUID
    id: UUID
    user_id: UUID
