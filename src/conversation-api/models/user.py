from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class UserModel(BaseModel):
    email: Optional[str] = None
    external_id: str
    id: UUID = Field(default_factory=uuid4)
    login_hint: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
