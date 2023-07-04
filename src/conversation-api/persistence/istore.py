from models.conversation import GetConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel
from models.user import UserModel
from abc import ABC, abstractmethod
from typing import List, Union
from uuid import UUID


class IStore(ABC):
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
    def message_set(self, message: MessageModel, conversation_id: UUID) -> None:
        pass

    @abstractmethod
    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        pass
