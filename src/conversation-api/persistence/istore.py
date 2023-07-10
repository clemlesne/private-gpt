from abc import ABC, abstractmethod
from enum import Enum
from models.conversation import GetConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from typing import List, Union
from uuid import UUID


class StoreImplementation(str, Enum):
    COSMOS = "cosmos"
    REDIS = "redis"


class IStore(ABC):
    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    async def user_get(self, user_external_id: str) -> Union[UserModel, None]:
        pass

    @abstractmethod
    async def user_set(self, user: UserModel) -> None:
        pass

    @abstractmethod
    async def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Union[GetConversationModel, None]:
        pass

    @abstractmethod
    async def message_get_index(
        self, messages: List[IndexMessageModel]
    ) -> List[MessageModel]:
        pass

    @abstractmethod
    async def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def conversation_set(self, conversation: StoredConversationModel) -> None:
        pass

    @abstractmethod
    async def conversation_list(self, user_id: UUID) -> List[StoredConversationModel]:
        pass

    @abstractmethod
    async def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Union[MessageModel, None]:
        pass

    @abstractmethod
    async def message_set(self, message: StoredMessageModel) -> None:
        pass

    @abstractmethod
    async def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        pass

    @abstractmethod
    async def usage_set(self, usage: UsageModel) -> None:
        pass
