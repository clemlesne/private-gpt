from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class UsageModel(BaseModel):
    ai_model: str
    conversation_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    id: UUID = Field(default_factory=uuid4)
    prompt_name: Optional[str] = None
    tokens: int
    user_id: UUID  # Partition key
