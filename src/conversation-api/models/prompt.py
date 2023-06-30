from typing import List
from pydantic import BaseModel
from uuid import UUID


class BasePromptModel(BaseModel):
    id: UUID
    name: str


class StoredPromptModel(BasePromptModel):
    content: str


class ListPromptsModel(BaseModel):
    prompts: List[BasePromptModel]
