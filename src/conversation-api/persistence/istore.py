from abc import ABC, abstractmethod
from enum import Enum
from models.conversation import GetConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from models.memory import MemoryModel
from typing import List, Union
from uuid import UUID


class StoreImplementation(str, Enum):
    COSMOS = "cosmos"
    REDIS = "redis"


class IStore(ABC):
    @abstractmethod
    def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def user_get(self, user_external_id: str) -> Union[UserModel, None]:
        pass

    @abstractmethod
    def user_set(self, user: UserModel) -> None:
        pass

    @abstractmethod
    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Union[GetConversationModel, None]:
        pass

    @abstractmethod
    def message_get_index(
        self, messages: List[IndexMessageModel]
    ) -> List[MessageModel]:
        pass

    @abstractmethod
    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    def conversation_set(self, conversation: StoredConversationModel) -> None:
        pass

    @abstractmethod
    def conversation_list(self, user_id: UUID) -> List[StoredConversationModel]:
        pass

    @abstractmethod
    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Union[MessageModel, None]:
        pass

    @abstractmethod
    def message_set(self, message: StoredMessageModel) -> None:
        pass

    @abstractmethod
    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        pass

    @abstractmethod
    def usage_set(self, usage: UsageModel) -> None:
        pass

    @abstractmethod
    def memory_get(self, key: str, user_id: UUID) -> Union[MemoryModel, None]:
        pass

    @abstractmethod
    def memory_set(self, memory: MemoryModel) -> None:
        pass
