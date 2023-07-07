# Import utils
from utils import build_logger, get_config

# Import misc
from .istore import IStore
from azure.cosmos import CosmosClient, PartitionKey, ConsistencyLevel
from azure.cosmos.database import DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceExistsError
from azure.identity import DefaultAzureCredential
from datetime import datetime
from models.conversation import StoredConversationModel, StoredConversationModel
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.user import UserModel
from models.usage import UsageModel
from typing import (Any, Dict, List, Union)
from uuid import UUID


logger = build_logger(__name__)
SECRET_TTL_SECS = 60 * 60 * 24  # 1 day

# Configuration
CONVERSATION_PREFIX = "conversation"
DB_URL = get_config("cosmos", "url", str, required=True)
DB_NAME = get_config("cosmos", "database", str, required=True)

# Cosmos DB Client
credential = DefaultAzureCredential()
client = CosmosClient(url=DB_URL, credential=credential, consistency_level=ConsistencyLevel.Session)
database = client.get_database_client(DB_NAME)
conversation_client = database.get_container_client("conversation")
message_client = database.get_container_client("message")
user_client = database.get_container_client("user")
usage_client = database.get_container_client("usage")
logger.info(f'Connected to Cosmos DB at "{DB_URL}"')


class CosmosStore(IStore):
    def user_get(self, user_external_id: str) -> Union[UserModel, None]:
        query = f"SELECT * FROM c WHERE c.external_id = '{user_external_id}'"
        items = user_client.query_items(query=query, partition_key="dummy")
        try:
            raw = next(items)
            return UserModel(**raw)
        except StopIteration:
            return None

    def user_set(self, user: UserModel) -> None:
        user_client.upsert_item(body={
            **self._sanitize_before_insert(user.dict()),
            "dummy": "dummy",
        })

    def conversation_get(
        self, conversation_id: UUID, user_id: UUID
    ) -> Union[StoredConversationModel, None]:
        try:
            raw = conversation_client.read_item(
                item=str(conversation_id), partition_key=str(user_id)
            )
            return StoredConversationModel(**raw)
        except CosmosHttpResponseError:
            return None

    def conversation_exists(self, conversation_id: UUID, user_id: UUID) -> bool:
        return self.conversation_get(conversation_id, user_id) is not None

    def conversation_set(self, conversation: StoredConversationModel) -> None:
        conversation_client.upsert_item(body=self._sanitize_before_insert(conversation.dict()))

    def conversation_list(self, user_id: UUID) -> List[StoredConversationModel]:
        query = f"SELECT * FROM c WHERE c.user_id = '{user_id}' ORDER BY c.created_at DESC"
        items = conversation_client.query_items(query=query, enable_cross_partition_query=True)
        return [StoredConversationModel(**item) for item in items]

    def message_get(
        self, message_id: UUID, conversation_id: UUID
    ) -> Union[MessageModel, None]:
        try:
            raw = message_client.read_item(item=str(message_id), partition_key=str(conversation_id))
            return MessageModel(**raw)
        except CosmosHttpResponseError:
            return None

    def message_get_index(
        self, message_indexs: List[IndexMessageModel]
    ) -> List[MessageModel]:
        messages = []
        for message_index in message_indexs:
            try:
                raw = message_client.read_item(
                    item=str(message_index.id), partition_key=str(message_index.conversation_id)
                )
                messages.append(MessageModel(**raw))
            except CosmosHttpResponseError:
                pass
        return messages

    def message_set(self, message: StoredMessageModel) -> None:
        expiry = SECRET_TTL_SECS if message.secret else None
        message_client.upsert_item(body={
            **self._sanitize_before_insert(message.dict()),
            "_ts": expiry, # TTL in seconds
        })

    def message_list(self, conversation_id: UUID) -> List[MessageModel]:
        query = f"SELECT * FROM c WHERE c.conversation_id = '{conversation_id}' ORDER BY c.created_at ASC"
        items = message_client.query_items(query=query, enable_cross_partition_query=True)
        return [MessageModel(**item) for item in items]

    def usage_set(self, usage: UsageModel) -> None:
        usage_client.upsert_item(body=self._sanitize_before_insert(usage.dict()))

    def _sanitize_before_insert(self, item: dict) -> Dict[str, Union[str, int, float, bool]]:
        for key, value in item.items():
            if isinstance(value, UUID):
                item[key] = str(value)
            elif isinstance(value, datetime):
                item[key] = value.isoformat()
        return item
