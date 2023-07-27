from pydantic import BaseModel, Field
from typing import List
from uuid import UUID, uuid4


class BasePromptModel(BaseModel):
    group: str
    id: UUID = Field(default_factory=uuid4)
    name: str


class StoredPromptModel(BasePromptModel):
    content: str


class ListPromptsModel(BaseModel):
    prompts: List[BasePromptModel]
