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
    store: IStore

    def __init__(self, store: IStore):
        self.store = store

    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def message_search(
        self, query: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        pass

    @abstractmethod
    def message_index(self, message: StoredMessageModel) -> None:
        pass
