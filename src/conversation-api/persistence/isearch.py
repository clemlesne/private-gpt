from .istore import IStore
from abc import ABC, abstractmethod
from models.message import MessageModel
from models.search import SearchModel
from uuid import UUID


class ISearch(ABC):
    def __init__(self, store: IStore):
        self.store = store

    @abstractmethod
    def message_search(self, query: str, user_id: UUID) -> SearchModel[MessageModel]:
        pass

    @abstractmethod
    def message_index(self, message: MessageModel, conversation_id: UUID, user_id: UUID) -> None:
        pass
