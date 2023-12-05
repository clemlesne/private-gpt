from ai.openai import OpenAI
from datetime import datetime
from helpers.config_models.persistence import QdrantModel
from helpers.logging import build_logger
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.search import SearchModel, SearchStatsModel, SearchAnswerModel
from persistence.icache import ICache
from persistence.isearch import ISearch
from persistence.istore import IStore
from pydantic import ValidationError
from qdrant_client import QdrantClient, AsyncQdrantClient
from uuid import UUID, uuid4
import qdrant_client.http.models as qmodels
import textwrap
import time


_logger = build_logger(__name__)
CACHE_TTL_SECS = 60 * 60 * 24 * 7  # 1 week
QD_DIMENSION = 1536
QD_METRIC = qmodels.Distance.DOT


# TODO: Async functions to avoid UX blocking
class QdrantSearch(ISearch):
    _openai: OpenAI

    def __init__(
        self, config: QdrantModel, store: IStore, cache: ICache, openai: OpenAI
    ):
        super().__init__(store, cache)

        kwargs = {
            "host": config.host,
            "https": config.https,
            "port": config.port,
            "prefer_grpc": config.prefer_grpc,
            "timeout": 5,
        }
        self._client = QdrantClient(**kwargs)
        self._aclient = AsyncQdrantClient(**kwargs)
        self._collection = config.collection
        self._openai = openai

        # Ensure collection exists
        try:
            self._client.get_collection(self._collection)
            _logger.debug(f"Collection {self._collection} already exists")
        except Exception:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    distance=QD_METRIC,
                    size=QD_DIMENSION,
                ),
            )
            _logger.debug(f"Collection {self._collection} created")

    async def areadiness(self) -> ReadinessStatus:
        try:
            tmp_id = str(uuid4())
            await self._aclient.upsert(
                collection_name=self._collection,
                points=[
                    qmodels.PointStruct(
                        vector=[0.0] * QD_DIMENSION,
                        payload={},
                        id=tmp_id,
                    )
                ],
            )
            await self._aclient.retrieve(collection_name=self._collection, ids=[tmp_id])
            await self._aclient.delete(
                collection_name=self._collection, points_selector=[tmp_id]
            )
        except Exception:
            _logger.warn("Error connecting to Qdrant", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    def message_search(
        self, q: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        _logger.debug(f"Searching for: {q}")
        start = time.monotonic()
        cache_key = f"message-search:{user_id}:{q}:{limit}"

        try:
            if self.cache.exists(cache_key):
                _logger.debug(f'Cache hit for search message "{q}"')
                return SearchModel[MessageModel].model_validate_json(
                    self.cache.get(cache_key)
                )
        except ValidationError as e:
            _logger.warn(f'Error parsing message search from cache, "{e}"')

        conversations = self.store.conversation_list(user_id) or []
        vector = self._openai.vector_from_text(
            textwrap.dedent(
                f"""
            Today, we are the {datetime.utcnow()}. {q.capitalize()}
        """
            )
        )
        count = self._client.count(collection_name=self._collection, exact=False).count
        raws = self._client.search(
            collection_name=self._collection,
            limit=limit,
            query_filter=qmodels.Filter(
                should=[
                    qmodels.FieldCondition(
                        key="conversation_id", match=qmodels.MatchValue(value=str(c.id))
                    )
                    for c in conversations
                ]
            ),
            query_vector=vector,
            search_params=qmodels.SearchParams(hnsw_ef=128, exact=False),
        )

        _logger.debug(f"Got {len(raws)} results from Qdrant")

        index_messages = []
        for raw in raws:
            try:
                index_messages.append(IndexMessageModel(**raw.payload))
            except ValidationError as e:
                _logger.warn(f'Error parsing index message, "{e}"')

        messages = self.store.message_get_index(index_messages) or []
        _logger.debug(f"Messages: {messages}")

        search = SearchModel[MessageModel](
            answers=[
                SearchAnswerModel[MessageModel](data=m, score=s)
                for m, s in zip(messages, [raw.score for raw in raws])
            ],
            query=q,
            stats=SearchStatsModel(total=count, time=time.monotonic() - start),
        )
        # Update cache
        self.cache.set(cache_key, search.model_dump_json(), CACHE_TTL_SECS)
        return search

    async def message_aindex(self, message: StoredMessageModel) -> None:
        _logger.debug(f'Indexing message "{message.id}"')
        vector = self._openai.vector_from_text(message.content)
        index = IndexMessageModel(
            conversation_id=message.conversation_id,
            id=message.id,
        )

        await self._aclient.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=message.id.hex, payload=index.model_dump(), vector=vector
                )
            ],
        )
