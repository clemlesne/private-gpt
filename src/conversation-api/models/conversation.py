from .message import MessageModel
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class BaseConversationModel(BaseModel):
    created_at: datetime
    id: UUID
    title: Optional[str] = None
    user_id: UUID


class GetConversationModel(BaseConversationModel):
    messages: List[MessageModel]


class SearchConversationModel(BaseModel):
    conversations: List[BaseConversationModel]
