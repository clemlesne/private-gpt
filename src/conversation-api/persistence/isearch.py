from .istore import IStore
from abc import ABC, abstractmethod
from enum import Enum
from models.message import MessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.search import SearchModel
from uuid import UUID


class SearchImplementation(str, Enum):
    QDRANT = "qdrant"


class ISearch(ABC):
    def __init__(self, store: IStore):
        self.store = store

    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    async def message_search(
        self, query: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        pass

    @abstractmethod
    async def message_index(self, message: StoredMessageModel, user_id: UUID) -> None:
        pass
