from .message import MessageModel
from .prompt import StoredPromptModel, BasePromptModel
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4


class BaseConversationModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    id: UUID = Field(default_factory=uuid4)
    title: Optional[str] = None
    user_id: UUID  # Partition key


class StoredConversationModel(BaseConversationModel):
    prompt: Optional[StoredPromptModel] = None


class GetConversationModel(BaseConversationModel):
    messages: List[MessageModel]
    prompt: Optional[BasePromptModel] = None


class ListConversationsModel(BaseModel):
    conversations: List[BaseConversationModel]
