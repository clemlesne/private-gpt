# Import utils
from utils import build_logger, get_config

# Import misc
from .isearch import ISearch
from .istore import IStore
from ai.openai import OpenAI
from datetime import datetime
from models.message import MessageModel, IndexMessageModel, StoredMessageModel
from models.readiness import ReadinessStatus
from models.search import SearchModel, SearchStatsModel, SearchAnswerModel
from qdrant_client import QdrantClient
from uuid import UUID, uuid4
import asyncio
import qdrant_client.http.models as qmodels
import textwrap
import time


_logger = build_logger(__name__)
QD_COLLECTION = "messages"
QD_DIMENSION = 1536
QD_HOST = get_config(["persistence", "qdrant"], "host", str, required=True)
QD_PORT = 6333
QD_METRIC = qmodels.Distance.DOT
client = QdrantClient(host=QD_HOST, port=6333)


class QdrantSearch(ISearch):
    _loop: asyncio.AbstractEventLoop
    openai: OpenAI

    def __init__(self, store: IStore, openai: OpenAI):
        super().__init__(store)

        self._loop = asyncio.get_running_loop()
        self.openai = openai

        # Ensure collection exists
        try:
            client.get_collection(QD_COLLECTION)
        except Exception:
            client.create_collection(
                collection_name=QD_COLLECTION,
                vectors_config=qmodels.VectorParams(
                    distance=QD_METRIC,
                    size=QD_DIMENSION,
                ),
            )

    async def readiness(self) -> ReadinessStatus:
        try:
            tmp_id = str(uuid4())
            client.upsert(
                collection_name=QD_COLLECTION,
                points=[
                    qmodels.PointStruct(
                        vector=[0.0] * QD_DIMENSION,
                        payload={},
                        id=tmp_id,
                    )
                ],
            )
            client.retrieve(collection_name=QD_COLLECTION, ids=[tmp_id])
            client.delete(collection_name=QD_COLLECTION, points_selector=[tmp_id])
        except Exception:
            _logger.warn("Error connecting to Qdrant", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    def message_search(
        self, q: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        _logger.debug(f"Searching for: {q}")
        start = time.monotonic()

        conversations = self.store.conversation_list(user_id)

        vector = self.openai.vector_from_text(
            textwrap.dedent(
                f"""
            Today, we are the {datetime.utcnow()}. {q.capitalize()}
        """
            )
        )

        total = client.count(collection_name=QD_COLLECTION, exact=False).count
        raws = client.search(
            collection_name=QD_COLLECTION,
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
            except Exception:
                _logger.warn("Error parsing index message", exc_info=True)

        messages = self.store.message_get_index(index_messages)
        _logger.debug(f"Messages: {messages}")

        return SearchModel[MessageModel](
            answers=[
                SearchAnswerModel[MessageModel](data=m, score=s)
                for m, s in zip(messages, [raw.score for raw in raws])
            ],
            query=q,
            stats=SearchStatsModel(total=total, time=time.monotonic() - start),
        )

    def message_index(self, message: StoredMessageModel) -> None:
        _logger.debug(f'Indexing message "{message.id}"')
        self._loop.create_task(self._index_background(message))

    async def _index_background(self, message: StoredMessageModel) -> None:
        _logger.debug(f"Starting indexing worker for message: {message.id}")

        vector = self.openai.vector_from_text(message.content)
        index = IndexMessageModel(
            conversation_id=message.conversation_id,
            id=message.id,
        )

        client.upsert(
            collection_name=QD_COLLECTION,
            points=[
                qmodels.PointStruct(id=message.id.hex, payload=index, vector=vector)
            ],
        )
