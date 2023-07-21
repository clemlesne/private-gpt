from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class MemoryModel(BaseModel):
    created_at: datetime
    id: UUID
    key: str
    user_id: UUID # Partition key
    value: Optional[str] = None
