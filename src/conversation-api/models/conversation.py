from .message import MessageModel
from .prompt import StoredPromptModel, BasePromptModel
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class BaseConversationModel(BaseModel):
    created_at: datetime
    id: UUID
    title: Optional[str] = None
    user_id: UUID # Partition key


class StoredConversationModel(BaseConversationModel):
    prompt: Optional[StoredPromptModel] = None


class GetConversationModel(BaseConversationModel):
    messages: List[MessageModel]
    prompt: Optional[BasePromptModel] = None


class ListConversationsModel(BaseModel):
    conversations: List[BaseConversationModel]
