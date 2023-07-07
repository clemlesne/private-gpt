from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class UsageModel(BaseModel):
    ai_model: str
    conversation_id: UUID
    created_at: datetime
    id: UUID
    prompt_name: Optional[str] = None
    tokens: int
    user_id: UUID # Partition key

