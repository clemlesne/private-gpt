# Import utils
from utils import logger

from models.conversation import GetConversationModel, BaseConversationModel
from models.message import MessageModel
from models.user import UserModel
from .istore import IStore
from .istream import IStream
from redis import Redis
from typing import AsyncGenerator, Callable, List, Literal, Optional
from uuid import UUID
import asyncio
import os


###
# Init Redis
###

CACHE_TTL_SECS = 60 * 60  # 1 hour
CONVERSATION_PREFIX = "conversation"
MESSAGE_PREFIX = "message"
STREAM_PREFIX = "stream"
STREAM_STOPWORD = "STOP"
REDIS_HOST = os.environ.get("MS_REDIS_HOST")
REDIS_PORT = 6379
USER_PREFIX = "user"
client = Redis(db=0, host=REDIS_HOST, port=REDIS_PORT)


class RedisStore(IStore):
    def user_get(self, user_external_id: str) -> UserModel:
        raw = client.get(self._user_cache_key(user_external_id))
        if raw is None:
            return None
        return UserModel.parse_raw(raw)


    def user_set(self, user: UserModel) -> None:
        client.set(self._user_cache_key(user.external_id), user.json(), ex=CACHE_TTL_SECS)


    def conversation_get(self, conversation_id: UUID, user_id: UUID) -> GetConversationModel:
        raw = client.get(self._conversation_cache_key(user_id, conversation_id))
        if raw is None:
            return None
        base_conversation = BaseConversationModel.parse_raw(raw)
        messages = self.message_list(conversation_id)
        return GetConversationModel(
            **base_conversation.dict(),
            messages=messages,
        )


    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return client.exists(self._conversation_cache_key(user_id, conversation_id))


    def conversation_set(self, conversation: BaseConversationModel) -> None:
        client.set(self._conversation_cache_key(conversation.user_id, conversation.id), conversation.json(), ex=CACHE_TTL_SECS)


    def conversation_list(self, user_id: UUID) -> List[BaseConversationModel]:
        keys = client.keys(f"{self._conversation_cache_key(user_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        conversations = []
        for raw in raws:
            try:
                conversations.append(BaseConversationModel.parse_raw(raw))
            except Exception:
                logger.warn("Error parsing conversation", exc_info=True)
        # Sort by created_at desc
        conversations.sort(key=lambda x: x.created_at, reverse=True)
        return conversations


    def message_get(self, message_id: UUID, conversation_id: UUID) -> MessageModel:
        raw = client.get(self._message_cache_key(conversation_id, message_id))
        if raw is None:
            return None
        return MessageModel.parse_raw(raw)


    def message_set(self, message: MessageModel, conversation_id: UUID) -> None:
        client.set(self._message_cache_key(conversation_id, message.id), message.json(), ex=CACHE_TTL_SECS)


    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        keys = client.keys(f"{self._message_cache_key(conversation_id)}:*")
        raws = client.mget(keys)
        if raws is None:
            return []
        messages = []
        for raw in raws:
            try:
                messages.append(MessageModel.parse_raw(raw))
            except Exception:
                logger.warn("Error parsing conversation", exc_info=True)
        # Sort by created_at asc
        messages.sort(key=lambda x: x.created_at)
        return messages


    def _conversation_cache_key(self, user_id: UUID, conversation_id: Optional[UUID] = None) -> str:
        if not conversation_id:
            return f"{CONVERSATION_PREFIX}:{user_id.hex}"
        return f"{CONVERSATION_PREFIX}:{user_id.hex}:{conversation_id.hex}"


    def _message_cache_key(self, conversation_id: UUID, message_id: Optional[UUID] = None) -> str:
        if not message_id:
            return f"{MESSAGE_PREFIX}:{conversation_id.hex}"
        return f"{MESSAGE_PREFIX}:{conversation_id.hex}:{message_id.hex}"


    def _user_cache_key(self, user_external_id: str) -> str:
        return f"{USER_PREFIX}:{user_external_id}"


class RedisStream(IStream):
    def push(self, content: str, token: UUID) -> None:
        client.xadd(self._cache_key(token), {"message": content})


    async def get(self, token: UUID, loop_func: Callable[[], bool]) -> AsyncGenerator[any | Literal["STOP"], None]:
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
                streams={message_key: stream_id},
                block=10_000,  # Wait 10 seconds
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

            await asyncio.sleep(0.25)

        # Send the end of stream message
        yield STREAM_STOPWORD


    def clean(self, token: UUID) -> None:
        client.delete(self._cache_key(token))


    def _cache_key(self, token: UUID) -> str:
        return f"{STREAM_PREFIX}:{token.hex}"
