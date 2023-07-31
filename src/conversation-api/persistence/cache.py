# Import utils
from utils import build_logger

# Import misc
from .istore import IStore
from models.conversation import StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from pydantic import ValidationError
from typing import List, Optional
from uuid import UUID


_logger = build_logger(__name__)


class CacheStore(IStore):
    CONVERSATION_PREFIX = "conversation"
    MESSAGE_PREFIX = "message"
    SECRET_TTL_SECS = 60 * 60 * 24  # 1 day
    USAGE_PREFIX = "usage"
    USER_PREFIX = "user"

    async def readiness(self) -> ReadinessStatus:
        return await self.cache.readiness()

    def user_get(self, user_external_id: str) -> Optional[UserModel]:
        key = self._user_key(user_external_id)
        if not self.cache.exists(key):
            return None
        return UserModel.parse_raw(self.cache.get(self._user_key(user_external_id)))

    def user_set(self, user: UserModel) -> None:
        self.cache.set(self._user_key(user.external_id), user.json())

    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[StoredConversationModel]:
        key = self._conversation_key(user_id, conversation_id)
        if not self.cache.exists(key):
            return None
        StoredConversationModel.parse_raw(
            self.cache.get(self._conversation_key(user_id, conversation_id))
        )

    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        key = self._conversation_key(user_id, conversation_id)
        return self.cache.exists(key) != 0

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        key = self._conversation_key(conversation.user_id, conversation.id)
        self.cache.set(key, conversation.json())

    def conversation_list(
        self, user_id: UUID
    ) -> Optional[List[StoredConversationModel]]:
        key = f"{self._conversation_key(user_id)}:*"
        if not self.cache.exists(key):
            return None
        conversations = []
        for raws in (self.cache.hget(key) or {}).values():
            try:
                conversations.append(StoredConversationModel.parse_raw(raws))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        return conversations or None

    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Optional[MessageModel]:
        key = self._message_key(conversation_id, message_id)
        if not self.cache.exists(key):
            return None
        return MessageModel.parse_raw(self.cache.get(key))

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> Optional[List[MessageModel]]:
        keys = [
            self._message_key(message_index.conversation_id, message_index.id)
            for message_index in message_indexs
        ]
        raws = self.cache.mget(keys)
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.parse_raw(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing message, "{e}"')
        return messages or None

    def message_set(self, message: StoredMessageModel) -> None:
        key = self._message_key(message.conversation_id, message.id)
        expiry = self.SECRET_TTL_SECS if message.secret else None
        self.cache.set(key, message.json(), expiry)

    def message_list(self, conversation_id: UUID) -> Optional[List[MessageModel]]:
        key = f"{self._message_key(conversation_id)}:*"
        raws = self.cache.mget(key)
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.parse_raw(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        return messages or None

    def usage_set(self, usage: UsageModel) -> None:
        key = self._usage_key(usage.user_id)
        self.cache.set(key, usage.json())

    def _usage_key(self, user_id: UUID) -> str:
        return f"{self.USAGE_PREFIX}:{user_id.hex}"

    def _conversation_key(
        self, user_id: UUID, conversation_id: Optional[UUID] = None
    ) -> str:
        if not conversation_id:
            return f"{self.CONVERSATION_PREFIX}:{user_id.hex}"
        return f"{self.CONVERSATION_PREFIX}:{user_id.hex}:{conversation_id.hex}"

    def _message_key(
        self, conversation_id: UUID, message_id: Optional[UUID] = None
    ) -> str:
        if not message_id:
            return f"{self.MESSAGE_PREFIX}:{conversation_id.hex}"
        return f"{self.MESSAGE_PREFIX}:{conversation_id.hex}:{message_id.hex}"

    def _user_key(self, user_external_id: str) -> str:
        return f"{self.USER_PREFIX}:{user_external_id}"
