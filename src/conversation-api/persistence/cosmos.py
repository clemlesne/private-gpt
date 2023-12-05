from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity import DefaultAzureCredential
from datetime import datetime
from helpers.config_models.persistence import CosmosModel
from helpers.logging import build_logger
from models.conversation import StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.usage import UsageModel
from models.user import UserModel
from persistence.icache import ICache
from persistence.istore import IStore
from pydantic import ValidationError
from typing import Any, List, Optional, Union
from uuid import UUID, uuid4


_logger = build_logger(__name__)
AZ_CREDENTIAL = DefaultAzureCredential()
CONVERSATION_PREFIX = "conversation"
SECRET_TTL_SECS = 60 * 60 * 24  # 1 day


# TODO: Async functions to avoid UX blocking
class CosmosStore(IStore):
    def __init__(self, config: CosmosModel, cache: ICache):
        super().__init__(cache)

        client = CosmosClient(
            connection_timeout=5,
            consistency_level=config.consistency,
            credential=AZ_CREDENTIAL,
            url=config.url,
        )
        database = client.get_database_client(config.database)

        self._conversation_client = database.get_container_client("conversation")
        self._memory_client = database.get_container_client("memory")
        self._message_client = database.get_container_client("message")
        self._usage_client = database.get_container_client("usage")
        self._user_client = database.get_container_client("user")

    async def areadiness(self) -> ReadinessStatus:
        try:
            # Cosmos DB is not ACID compliant, so we can't use transactions
            self._conversation_client.upsert_item(
                body={
                    "dummy": "dummy",
                    "id": str(uuid4()),
                }
            )
        except CosmosHttpResponseError:
            _logger.warn("Error connecting to Cosmos", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    async def user_aget(self, user_external_id: str) -> Optional[UserModel]:
        cache_key = f"user:{user_external_id}"

        try:
            if await self.cache.aexists(cache_key):
                _logger.debug(f'Cache hit for user "{user_external_id}"')
                return UserModel.model_validate_json(await self.cache.aget(cache_key))
        except ValidationError as e:
            _logger.warn(f'Error parsing user from cache, "{e}"')

        query = f"SELECT * FROM c WHERE c.external_id = '{user_external_id}'"
        items = self._user_client.query_items(query=query, partition_key="dummy")
        try:
            raw = next(items)
            user = UserModel(**raw)
            # Update cache
            await self.cache.aset(cache_key, user.model_dump_json())
            return user
        except StopIteration:
            return None

    async def user_aset(self, user: UserModel) -> None:
        cache_key = f"user:{user.external_id}"
        self._user_client.upsert_item(
            body={
                **self._sanitize_before_insert(user.model_dump()),
                "dummy": "dummy",
            }
        )
        # Update cache
        await self.cache.aset(cache_key, user.model_dump_json())

    async def conversation_aget(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[StoredConversationModel]:
        cache_key = f"conversation:{user_id}:{conversation_id}"

        try:
            if await self.cache.aexists(cache_key):
                _logger.debug(f'Cache hit for conversation "{conversation_id}"')
                return StoredConversationModel.model_validate_json(
                    await self.cache.aget(cache_key)
                )
        except ValidationError as e:
            _logger.warn(f'Error parsing conversation from cache, "{e}"')

        try:
            raw = self._conversation_client.read_item(
                item=str(conversation_id), partition_key=str(user_id)
            )
            conversation = StoredConversationModel(**raw)
            # Update cache
            await self.cache.aset(cache_key, conversation.model_dump_json())
            return conversation
        except CosmosHttpResponseError:
            return None

    async def conversation_aexists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return await self.conversation_aget(conversation_id, user_id) != None

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        cache_key = f"conversation:{conversation.user_id}:{conversation.id}"
        self._conversation_client.upsert_item(
            body=self._sanitize_before_insert(conversation.model_dump())
        )
        # Update cache
        self.cache.set(cache_key, conversation.model_dump_json())
        self.cache.delete(
            f"conversation-list:{conversation.user_id}"
        )  # Invalidate list

    def conversation_list(
        self, user_id: UUID
    ) -> Optional[List[StoredConversationModel]]:
        cache_key = f"conversation-list:{user_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for conversation list "{user_id}"')
                return [
                    StoredConversationModel.model_validate_json(raw)
                    for _, raw in (self.cache.hget(cache_key) or {}).items()
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing conversation list from cache, "{e}"')

        query = (
            f"SELECT * FROM c WHERE c.user_id = '{user_id}' ORDER BY c.created_at DESC"
        )
        raws = self._conversation_client.query_items(
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
        self.cache.hset(
            cache_key, {str(c.id): c.model_dump_json() for c in conversations}
        )
        return conversations or None

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> Optional[List[MessageModel]]:
        cache_keys = [f"message:{m.conversation_id}:{m.id}" for m in message_indexs]

        try:
            if all(self.cache.exists(k) for k in cache_keys):
                _logger.debug(f'Cache hit for message index "{message_indexs}"')
                return [
                    MessageModel.model_validate_json(self.cache.get(k))
                    for k in cache_keys
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing message index from cache, "{e}"')

        messages = []
        for message_index in message_indexs:
            try:
                raw = self._message_client.read_item(
                    item=str(message_index.id),
                    partition_key=str(message_index.conversation_id),
                )
                messages.append(MessageModel(**raw))
            except CosmosHttpResponseError:
                pass
        # Update cache
        self.cache.mset({k: m.model_dump_json() for k, m in zip(cache_keys, messages)})
        return messages or None

    def message_set(self, message: StoredMessageModel) -> None:
        cache_key = f"message:{message.conversation_id}:{message.id}"
        expiry = SECRET_TTL_SECS if message.secret else None
        self._message_client.upsert_item(
            body={
                **self._sanitize_before_insert(message.model_dump()),
                "_ts": expiry,  # TTL in seconds
            }
        )
        # Update cache
        self.cache.set(cache_key, message.model_dump_json(), expiry)
        self.cache.delete(f"message-list:{message.conversation_id}")  # Invalidate list

    def message_list(self, conversation_id: UUID) -> Optional[List[MessageModel]]:
        cache_key = f"message-list:{conversation_id}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for message list "{conversation_id}"')
                return [
                    MessageModel.model_validate_json(raw)
                    for _, raw in (self.cache.hget(cache_key) or {}).items()
                ]
        except ValidationError as e:
            _logger.warn(f'Error parsing message list from cache, "{e}"')

        query = f"SELECT * FROM c WHERE c.conversation_id = '{conversation_id}' ORDER BY c.created_at ASC"
        raws = self._message_client.query_items(
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
        self.cache.hset(cache_key, {str(m.id): m.model_dump_json() for m in messages})
        return messages or None

    def usage_set(self, usage: UsageModel) -> None:
        _logger.debug(f'Usage set "{usage.id}"')
        self._usage_client.upsert_item(
            body=self._sanitize_before_insert(usage.model_dump())
        )

    def _sanitize_before_insert(self, item: Union[dict, Any]) -> Union[dict, Any]:
        for key, value in item.items() if isinstance(item, dict) else enumerate(item):
            if isinstance(value, UUID):
                item[key] = str(value)
            elif isinstance(value, datetime):
                item[key] = value.isoformat()
            elif isinstance(value, dict) or isinstance(value, list):
                item[key] = self._sanitize_before_insert(value)
        return item
