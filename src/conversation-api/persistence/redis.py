# Import utils
from utils import build_logger, get_config

# Import misc
from .istore import IStore
from .istream import IStream
from models.conversation import StoredConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from models.memory import MemoryModel
from redis import Redis
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Awaitable,
    List,
    Literal,
    Optional,
    Union,
)
from uuid import UUID, uuid4
import asyncio


logger = build_logger(__name__)
SECRET_TTL_SECS = 60 * 60 * 24  # 1 day

# Configuration
CONVERSATION_PREFIX = "conversation"
DB_HOST = get_config("redis", "host", str, required=True)
DB_PORT = 6379
STREAM_STOPWORD = "STOP"
MEMORY_PREFIX = "memory"
MESSAGE_PREFIX = "message"
STREAM_PREFIX = "stream"
USAGE_PREFIX = "usage"
USER_PREFIX = "user"

# Redis client
client = Redis(db=0, host=DB_HOST, port=DB_PORT)


class RedisStore(IStore):
    def readiness(self) -> ReadinessStatus:
        try:
            tmp_id = str(uuid4())
            client.set(tmp_id, "dummy")
            client.get(tmp_id)
            client.delete(tmp_id)
        except Exception:
            logger.warn("Error connecting to Redis", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    def user_get(self, user_external_id: str) -> Union[UserModel, None]:
        raw = client.get(self._user_cache_key(user_external_id))
        if raw is None:
            return None
        return UserModel.parse_raw(raw)

    def user_set(self, user: UserModel) -> None:
        client.set(self._user_cache_key(user.external_id), user.json())

    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Union[StoredConversationModel, None]:
        raw = client.get(self._conversation_cache_key(user_id, conversation_id))
        if raw is None:
            return None
        return StoredConversationModel.parse_raw(raw)

    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return (
            client.exists(self._conversation_cache_key(user_id, conversation_id)) != 0
        )

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        client.set(
            self._conversation_cache_key(conversation.user_id, conversation.id),
            conversation.json(),
        )

    def conversation_list(self, user_id: UUID) -> List[StoredConversationModel]:
        keys = client.keys(f"{self._conversation_cache_key(user_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        conversations = []
        for raw in raws:
            if raw is None:
                continue
            try:
                conversations.append(StoredConversationModel.parse_raw(raw))
            except Exception:
                logger.warn("Error parsing conversation", exc_info=True)
        # Sort by created_at desc
        conversations.sort(key=lambda x: x.created_at, reverse=True)
        return conversations

    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Union[MessageModel, None]:
        raw = client.get(self._message_cache_key(conversation_id, message_id))
        if raw is None:
            return None
        return MessageModel.parse_raw(raw)

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> List[MessageModel]:
        keys = [
            self._message_cache_key(message_index.conversation_id, message_index.id)
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
            except Exception:
                logger.warn("Error parsing message", exc_info=True)
        return messages

    def message_set(self, message: StoredMessageModel) -> None:
        expiry = SECRET_TTL_SECS if message.secret else None
        client.set(
            self._message_cache_key(message.conversation_id, message.id),
            message.json(),
            ex=expiry,
        )

    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        keys = client.keys(f"{self._message_cache_key(conversation_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel.parse_raw(raw))
            except Exception:
                logger.warn("Error parsing conversation", exc_info=True)
        # Sort by created_at asc
        messages.sort(key=lambda x: x.created_at)
        return messages

    def usage_set(self, usage: UsageModel) -> None:
        client.set(self._usage_cache_key(usage.user_id), usage.json())

    def memory_get(self, key: str, user_id: UUID) -> Union[MemoryModel, None]:
        raw = client.get(self._memory_cache_key(user_id, key))
        if raw is None:
            return None
        return MemoryModel.parse_raw(raw)

    def memory_set(self, memory: MemoryModel) -> None:
        client.set(self._memory_cache_key(memory.user_id, memory.key), memory.json())

    def _usage_cache_key(self, user_id: UUID) -> str:
        return f"{USAGE_PREFIX}:{user_id.hex}"

    def _conversation_cache_key(
        self, user_id: UUID, conversation_id: Optional[UUID] = None
    ) -> str:
        if not conversation_id:
            return f"{CONVERSATION_PREFIX}:{user_id.hex}"
        return f"{CONVERSATION_PREFIX}:{user_id.hex}:{conversation_id.hex}"

    def _message_cache_key(
        self, conversation_id: UUID, message_id: Optional[UUID] = None
    ) -> str:
        if not message_id:
            return f"{MESSAGE_PREFIX}:{conversation_id.hex}"
        return f"{MESSAGE_PREFIX}:{conversation_id.hex}:{message_id.hex}"

    def _user_cache_key(self, user_external_id: str) -> str:
        return f"{USER_PREFIX}:{user_external_id}"

    def _memory_cache_key(self, user_id: UUID, key: str) -> str:
        return f"{MEMORY_PREFIX}:{user_id.hex}:{key}"


class RedisStream(IStream):
    async def readiness(self) -> ReadinessStatus:
        try:
            client.set("dummy", "dummy")
            client.get("dummy")
            client.delete("dummy")
        except Exception:
            logger.warn("Error connecting to Redis", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    async def push(self, content: str, token: UUID) -> None:
        client.xadd(self._cache_key(token), {"message": content})

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

            message_key = self._cache_key(token)
            messages_raw = client.xread(
                block=10_000,  # Wait 10 seconds
                streams={message_key: stream_id},
            )

            if not messages_raw:
                break

            message_loop = ""
            for message_content in messages_raw[0][1]:
                stream_id = message_content[0]
                message = message_content[1][b"message"].decode("utf-8")
                if message == STREAM_STOPWORD:
                    is_end = True
                    break
                message_loop += message

            # Send the message to the client after the loop
            if message_loop:
                yield message_loop

            # 8 messages per second, enough for give a good user experience, but not too much for not using the thread too much
            await asyncio.sleep(0.125)

        # Send the end of stream message
        yield STREAM_STOPWORD

    async def clean(self, token: UUID) -> None:
        client.delete(self._cache_key(token))

    def _cache_key(self, token: UUID) -> str:
        return f"{STREAM_PREFIX}:{token.hex}"
