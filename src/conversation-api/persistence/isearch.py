from abc import ABC, abstractmethod
from enum import Enum
from models.message import MessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.search import SearchModel
from persistence.icache import ICache
from persistence.istore import IStore
from uuid import UUID


class SearchImplementation(str, Enum):
    QDRANT = "qdrant"


class ISearch(ABC):
    cache: ICache
    store: IStore

    def __init__(self, store: IStore, cache: ICache):
        self.cache = cache
        self.store = store

    @abstractmethod
    async def areadiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def message_search(
        self, query: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        pass

    @abstractmethod
    async def message_aindex(self, message: StoredMessageModel) -> None:
        pass
