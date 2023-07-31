from .icache import ICache
from abc import ABC, abstractmethod
from enum import Enum
from models.conversation import GetConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from typing import List, Optional
from uuid import UUID


class StoreImplementation(str, Enum):
    COSMOS = "cosmos"
    CACHE = "cache"


class IStore(ABC):
    cache: ICache

    def __init__(self, cache: ICache):
        self.cache = cache

    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def user_get(self, user_external_id: str) -> Optional[UserModel]:
        pass

    @abstractmethod
    def user_set(self, user: UserModel) -> None:
        pass

    @abstractmethod
    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[GetConversationModel]:
        pass

    @abstractmethod
    def message_get_index(
        self, messages: List[IndexMessageModel]
    ) -> Optional[List[MessageModel]]:
        pass

    @abstractmethod
    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    def conversation_set(self, conversation: StoredConversationModel) -> None:
        pass

    @abstractmethod
    def conversation_list(self, user_id: UUID) -> Optional[List[StoredConversationModel]]:
        pass

    @abstractmethod
    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Optional[MessageModel]:
        pass

    @abstractmethod
    def message_set(self, message: StoredMessageModel) -> None:
        pass

    @abstractmethod
    def message_list(self, conversation_id: UUID) -> Optional[List[MessageModel]]:
        pass

    @abstractmethod
    def usage_set(self, usage: UsageModel) -> None:
        pass
