from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID, uuid4


class MemoryModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    id: UUID = Field(default_factory=uuid4)
    key: str
    user_id: UUID  # Partition key
    value: Optional[str] = None
