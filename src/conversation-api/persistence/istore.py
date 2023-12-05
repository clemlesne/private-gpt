from abc import ABC, abstractmethod
from enum import Enum
from models.conversation import GetConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from persistence.icache import ICache
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
    async def areadiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    async def user_aget(self, user_external_id: str) -> Optional[UserModel]:
        pass

    @abstractmethod
    async def user_aset(self, user: UserModel) -> None:
        pass

    @abstractmethod
    async def conversation_aget(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[GetConversationModel]:
        pass

    @abstractmethod
    def message_get_index(
        self, messages: List[IndexMessageModel]
    ) -> Optional[List[MessageModel]]:
        pass

    @abstractmethod
    async def conversation_aexists(self, conversation_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    def conversation_set(self, conversation: StoredConversationModel) -> None:
        pass

    @abstractmethod
    def conversation_list(
        self, user_id: UUID
    ) -> Optional[List[StoredConversationModel]]:
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
