from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from uuid import UUID


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"


class MessageModel(BaseModel):
    content: str
    created_at: datetime
    id: UUID
    role: MessageRole
