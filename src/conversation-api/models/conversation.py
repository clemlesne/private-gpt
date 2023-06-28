from .message import MessageModel
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class ConversationModel(BaseModel):
    id: UUID
    messages: List[MessageModel]
    title: Optional[str] = None
    created_at: datetime


class SearchConversationModel(BaseModel):
    conversations: List[ConversationModel]
