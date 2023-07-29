# Import utils
from utils import build_logger, get_config

# Import misc
from .icache import ICache
from .istore import IStore
from .istream import IStream
from models.conversation import StoredConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from pydantic import ValidationError
from redis import Redis
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
)
from uuid import UUID, uuid4
import asyncio


_logger = build_logger(__name__)

# Configuration
DB_HOST = get_config(["persistence", "redis"], "host", str, required=True)
DB_PORT = 6379

# Redis client
client = Redis(db=0, host=DB_HOST, port=DB_PORT)


async def _readiness() -> ReadinessStatus:
    try:
        tmp_id = str(uuid4())
        client.set(tmp_id, "dummy")
        client.get(tmp_id)
        client.delete(tmp_id)
    except Exception:
        _logger.warn("Error connecting to Redis", exc_info=True)
        return ReadinessStatus.FAIL
    return ReadinessStatus.OK


class RedisStore(IStore):
    CONVERSATION_PREFIX = "conversation"
    MESSAGE_PREFIX = "message"
    SECRET_TTL_SECS = 60 * 60 * 24  # 1 day
    USAGE_PREFIX = "usage"
    USER_PREFIX = "user"

    async def readiness(self) -> ReadinessStatus:
        return await _readiness()

    def user_get(self, user_external_id: str) -> Optional[UserModel]:
        raw = client.get(self._user_key(user_external_id))
        if raw is None:
            return None
        return UserModel.parse_raw(raw)

    def user_set(self, user: UserModel) -> None:
        client.set(self._user_key(user.external_id), user.json())

    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[StoredConversationModel]:
        raw = client.get(self._conversation_key(user_id, conversation_id))
        if raw is None:
            return None
        return StoredConversationModel.parse_raw(raw)

    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return client.exists(self._conversation_key(user_id, conversation_id)) != 0

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        client.set(
            self._conversation_key(conversation.user_id, conversation.id),
            conversation.json(),
        )

    def conversation_list(self, user_id: UUID) -> List[StoredConversationModel]:
        keys = client.keys(f"{self._conversation_key(user_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        conversations = []
        for raw in raws:
            if raw is None:
                continue
            try:
                conversations.append(StoredConversationModel.parse_raw(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        # Sort by created_at desc
        conversations.sort(key=lambda x: x.created_at, reverse=True)
        return conversations

    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Optional[MessageModel]:
        raw = client.get(self._message_key(conversation_id, message_id))
        if raw is None:
            return None
        return MessageModel.parse_raw(raw)

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> List[MessageModel]:
        keys = [
            self._message_key(message_index.conversation_id, message_index.id)
            for message_index in message_indexs
        ]
        raws = client.mget(keys)
        if raws is None:
            return []
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.parse_raw(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing message, "{e}"')
        return messages

    def message_set(self, message: StoredMessageModel) -> None:
        expiry = self.SECRET_TTL_SECS if message.secret else None
        client.set(
            self._message_key(message.conversation_id, message.id),
            message.json(),
            ex=expiry,
        )

    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        keys = client.keys(f"{self._message_key(conversation_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.parse_raw(raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        # Sort by created_at asc
        messages.sort(key=lambda x: x.created_at)
        return messages

    def usage_set(self, usage: UsageModel) -> None:
        client.set(self._usage_key(usage.user_id), usage.json())

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


class RedisStream(IStream):
    STREAM_PREFIX = "stream"

    async def readiness(self) -> ReadinessStatus:
        return await _readiness()

    def push(self, content: str, token: UUID) -> None:
        client.xadd(self._key(token), {"message": content})

    async def get(
        self, token: UUID, loop_func: Callable[[], Awaitable[bool]]
    ) -> AsyncGenerator[Any | Literal["STOP"], None]:
        stream_id = 0
        is_end = False

        while True:
            # If the stream is ended, stop sending events
            if is_end:
                break

            if await loop_func():
                # If the loop function returns True, stop sending events
                break

            message_key = self._key(token)
            messages_raw = client.xread(
                block=10_000,  # Wait 10 seconds
                streams={message_key: stream_id},
            )

            if not messages_raw:
                break

            for message_content in messages_raw[0][1]:
                stream_id = message_content[0]
                message = message_content[1][b"message"].decode("utf-8")
                if message == self.stopword():
                    is_end = True
                    break
                yield message

            # 8 messages per second, enough for give a good user experience, but not too much for not using the thread too much
            await asyncio.sleep(0.125)

        # Send the end of stream message
        yield self.stopword()

    async def clean(self, token: UUID) -> None:
        client.delete(self._key(token))

    def _key(self, token: UUID) -> str:
        return f"{self.STREAM_PREFIX}:{token.hex}"


class RedisCache(ICache):
    CACHE_TTL_SECS = 60 * 24  # 1 hour

    async def readiness(self) -> ReadinessStatus:
        return await _readiness()

    def get(self, key: str) -> Optional[str]:
        raw = client.get(key)
        if raw is None:
            return None
        return raw.decode("utf-8")

    def set(self, key: str, value: str) -> None:
        client.set(key, value, ex=self.CACHE_TTL_SECS)

    def hget(self, key: str) -> Optional[Dict[str, str]]:
        raw = client.hgetall(key)
        if not raw:
            return None
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in raw.items()}

    def hset(self, key: str, mapping: Mapping[str, str]) -> None:
        client.hset(key, mapping=mapping)
        # TTL is not supported by hset, so we need to set it manually (https://github.com/redis/redis/issues/167#issuecomment-427708753)
        client.expire(key, self.CACHE_TTL_SECS)
