# Import utils
from utils import build_logger, get_config, AZ_CREDENTIAL

# Import misc
from .icache import ICache
from .istore import IStore
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from datetime import datetime
from models.conversation import StoredConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from pydantic import ValidationError
from typing import List, Optional, Union
from uuid import UUID, uuid4
import asyncio


_logger = build_logger(__name__)
SECRET_TTL_SECS = 60 * 60 * 24  # 1 day

# Configuration
CONVERSATION_PREFIX = "conversation"
DB_URL = get_config(["persistence", "cosmos"], "url", str, required=True)
DB_NAME = get_config(["persistence", "cosmos"], "database", str, required=True)

# Cosmos DB Client
client = CosmosClient(url=DB_URL, credential=AZ_CREDENTIAL)
database = client.get_database_client(DB_NAME)
conversation_client = database.get_container_client("conversation")
memory_client = database.get_container_client("memory")
message_client = database.get_container_client("message")
usage_client = database.get_container_client("usage")
user_client = database.get_container_client("user")


class CosmosStore(IStore):
    _loop: asyncio.AbstractEventLoop

    def __init__(self, cache: ICache):
        super().__init__(cache)

        self._loop = asyncio.get_running_loop()

    async def readiness(self) -> ReadinessStatus:
        try:
            # Cosmos DB is not ACID compliant, so we can't use transactions
            conversation_client.upsert_item(
                body={
                    "dummy": "dummy",
                    "id": str(uuid4()),
                }
            )
        except CosmosHttpResponseError:
            _logger.warn("Error connecting to Cosmos", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    def user_get(self, user_external_id: str) -> Optional[UserModel]:
        cache_key = f"user:{user_external_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for user "{user_external_id}"')
                return UserModel.parse_raw(self.cache.get(cache_key))
        except ValidationError as e:
            _logger.warn(f'Error parsing user from cache, "{e}"')

        query = f"SELECT * FROM c WHERE c.external_id = '{user_external_id}'"
        items = user_client.query_items(query=query, partition_key="dummy")
        try:
            raw = next(items)
            user = UserModel(**raw)
            # Update cache
            self.cache.set(cache_key, user.json())
            return user
        except StopIteration:
            return None

    def user_set(self, user: UserModel) -> None:
        cache_key = f"user:{user.external_id}"
        user_client.upsert_item(
            body={
                **self._sanitize_before_insert(user.dict()),
                "dummy": "dummy",
            }
        )
        # Update cache
        self.cache.set(cache_key, user.json())

    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[StoredConversationModel]:
        cache_key = f"conversation:{user_id}:{conversation_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for conversation "{conversation_id}"')
                return StoredConversationModel.parse_raw(self.cache.get(cache_key))
        except ValidationError as e:
            _logger.warn(f'Error parsing conversation from cache, "{e}"')

        try:
            raw = conversation_client.read_item(
                item=str(conversation_id), partition_key=str(user_id)
            )
            conversation = StoredConversationModel(**raw)
            # Update cache
            self.cache.set(cache_key, conversation.json())
            return conversation
        except CosmosHttpResponseError:
            return None

    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return self.conversation_get(conversation_id, user_id) != None

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        cache_key = f"conversation:{conversation.user_id}:{conversation.id}"
        conversation_client.upsert_item(
            body=self._sanitize_before_insert(conversation.dict())
        )
        # Update cache
        self.cache.set(cache_key, conversation.json())
        self.cache.delete(f"conversation-list:{conversation.user_id}")  # Invalidate list

    def conversation_list(self, user_id: UUID) -> Optional[List[StoredConversationModel]]:
        cache_key = f"conversation-list:{user_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for conversation list "{user_id}"')
                return [
                    StoredConversationModel.parse_raw(raw)
                    for _, raw in (self.cache.hget(cache_key) or {}).items()
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing conversation list from cache, "{e}"')

        query = (
            f"SELECT * FROM c WHERE c.user_id = '{user_id}' ORDER BY c.created_at DESC"
        )
        raws = conversation_client.query_items(
            query=query, enable_cross_partition_query=True
        )
        conversations = []
        for raw in raws:
            if raw is None:
                continue
            try:
                conversations.append(StoredConversationModel(**raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing conversation, "{e}"')
        # Update cache
        self.cache.hset(cache_key, {str(c.id): c.json() for c in conversations})
        return conversations or None

    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Optional[MessageModel]:
        cache_key = f"message:{conversation_id}:{message_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for message "{message_id}"')
                return MessageModel.parse_raw(self.cache.get(cache_key))
        except ValidationError as e:
            _logger.warn(f'Error parsing message from cache, "{e}"')

        try:
            raw = message_client.read_item(
                item=str(message_id), partition_key=str(conversation_id)
            )
            message = MessageModel(**raw)
            # Update cache
            self.cache.set(cache_key, message.json())
            return message
        except CosmosHttpResponseError:
            return None

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> Optional[List[MessageModel]]:
        cache_keys = [f"message:{m.conversation_id}:{m.id}" for m in message_indexs]

        try:
            if all(self.cache.exists(k) for k in cache_keys):
                _logger.debug(f'Cache hit for message index "{message_indexs}"')
                return [
                    MessageModel.parse_raw(self.cache.get(k)) for k in cache_keys
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing message index from cache, "{e}"')

        messages = []
        for message_index in message_indexs:
            try:
                raw = message_client.read_item(
                    item=str(message_index.id),
                    partition_key=str(message_index.conversation_id),
                )
                messages.append(MessageModel(**raw))
            except CosmosHttpResponseError:
                pass
        # Update cache
        self.cache.mset({k: m.json() for k, m in zip(cache_keys, messages)})
        return messages or None

    def message_set(self, message: StoredMessageModel) -> None:
        cache_key = f"message:{message.conversation_id}:{message.id}"
        expiry = SECRET_TTL_SECS if message.secret else None
        message_client.upsert_item(
            body={
                **self._sanitize_before_insert(message.dict()),
                "_ts": expiry,  # TTL in seconds
            }
        )
        # Update cache
        self.cache.set(cache_key, message.json(), expiry)
        self.cache.delete(f"message-list:{message.conversation_id}")  # Invalidate list

    def message_list(self, conversation_id: UUID) -> Optional[List[MessageModel]]:
        cache_key = f"message-list:{conversation_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for message list "{conversation_id}"')
                return [
                    MessageModel.parse_raw(raw)
                    for _, raw in (self.cache.hget(cache_key) or {}).items()
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing message list from cache, "{e}"')

        query = f"SELECT * FROM c WHERE c.conversation_id = '{conversation_id}' ORDER BY c.created_at ASC"
        raws = message_client.query_items(
            query=query, enable_cross_partition_query=True
        )
        messages = []
        for raw in raws:
            if raw is None:
                continue
            try:
                messages.append(MessageModel(**raw))
            except ValidationError as e:
                _logger.warn(f'Error parsing message, "{e}"')
        # Update cache
        self.cache.hset(cache_key, {str(m.id): m.json() for m in messages})
        return messages or None

    def usage_set(self, usage: UsageModel) -> None:
        _logger.debug(f'Usage set "{usage.id}"')
        self._loop.create_task(self._usage_set_background(usage))

    async def _usage_set_background(self, usage: UsageModel) -> None:
        usage_client.upsert_item(body=self._sanitize_before_insert(usage.dict()))

    def _sanitize_before_insert(self, item: Union[dict, list]) -> Union[dict, list]:
        for key, value in item.items() if isinstance(item, dict) else enumerate(item):
            if isinstance(value, UUID):
                item[key] = str(value)
            elif isinstance(value, datetime):
                item[key] = value.isoformat()
            elif isinstance(value, dict) or isinstance(value, list):
                item[key] = self._sanitize_before_insert(value)
        return item
