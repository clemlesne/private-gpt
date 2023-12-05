from helpers.logging import build_logger
from models.conversation import StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from persistence.istore import IStore
from pydantic import ValidationError
from typing import List, Optional
from uuid import UUID


_logger = build_logger(__name__)


class CacheStore(IStore):
    CONVERSATION_PREFIX: str = "conversation"
    MESSAGE_PREFIX: str = "message"
    SECRET_TTL_SECS: int = 60 * 60 * 24  # 1 day
    USAGE_PREFIX: str = "usage"
    USER_PREFIX: str = "user"

    async def areadiness(self) -> ReadinessStatus:
        return await self.cache.areadiness()

    async def user_aget(self, user_external_id: str) -> Optional[UserModel]:
        key = self._user_key(user_external_id)
        if not await self.cache.aexists(key):
            return None
        return UserModel.model_validate_json(
            await self.cache.aget(self._user_key(user_external_id))
        )

    async def user_aset(self, user: UserModel) -> None:
        await self.cache.aset(self._user_key(user.external_id), user.model_dump_json())

    async def conversation_aget(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[StoredConversationModel]:
        key = self._conversation_key(user_id, conversation_id)
        if not self.cache.exists(key):
            return None
        StoredConversationModel.model_validate_json(
            await self.cache.aget(self._conversation_key(user_id, conversation_id))
        )

    async def conversation_aexists(self, conversation_id: UUID, user_id: UUID) -> bool:
        key = self._conversation_key(user_id, conversation_id)
        return await self.cache.aexists(key) != 0

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        key = self._conversation_key(conversation.user_id, conversation.id)
        self.cache.set(key, conversation.model_dump_json())

    def conversation_list(
        self, user_id: UUID
    ) -> Optional[List[StoredConversationModel]]:
        key = f"{self._conversation_key(user_id)}:*"
        if not self.cache.exists(key):
            return None
        conversations = []
        for raws in (self.cache.hget(key) or {}).values():
            try:
                conversations.append(StoredConversationModel.model_validate_json(raws))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        return conversations or None

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
                messages.append(MessageModel.model_validate_json(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing message, "{e}"')
        return messages or None

    def message_set(self, message: StoredMessageModel) -> None:
        key = self._message_key(message.conversation_id, message.id)
        expiry = self.SECRET_TTL_SECS if message.secret else None
        self.cache.set(key, message.model_dump_json(), expiry)

    def message_list(self, conversation_id: UUID) -> Optional[List[MessageModel]]:
        key = f"{self._message_key(conversation_id)}:*"
        raws = self.cache.mget(key)
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.model_validate_json(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        return messages or None

    def usage_set(self, usage: UsageModel) -> None:
        key = self._usage_key(usage.user_id)
        self.cache.set(key, usage.model_dump_json())

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
