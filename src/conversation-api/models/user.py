from pydantic import BaseModel
from uuid import UUID


class UserModel(BaseModel):
    external_id: str
    id: UUID
