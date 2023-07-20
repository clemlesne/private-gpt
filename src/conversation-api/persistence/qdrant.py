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


logger = build_logger(__name__)
openai = OpenAI()
QD_COLLECTION = "messages"
QD_DIMENSION = 1536
QD_HOST = get_config("qd", "host", str, required=True)
QD_PORT = 6333
QD_METRIC = qmodels.Distance.DOT
client = QdrantClient(host=QD_HOST, port=6333)
logger.info(f'Connected to Qdrant at "{QD_HOST}:{QD_PORT}"')


class QdrantSearch(ISearch):
    def __init__(self, store: IStore):
        super().__init__(store)

        self._loop = asyncio.get_running_loop()

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
            logger.warn("Error connecting to Qdrant", exc_info=True)
            return ReadinessStatus.FAIL
        return ReadinessStatus.OK

    async def message_search(
        self, q: str, user_id: UUID, limit: int
    ) -> SearchModel[MessageModel]:
        logger.debug(f"Searching for: {q}")
        start = time.monotonic()

        conversations = await self.store.conversation_list(user_id)

        vector = await openai.vector_from_text(
            textwrap.dedent(
                f"""
                Today, we are the {datetime.utcnow()}. {q.capitalize()}
            """
            ),
            user_id,
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

        logger.debug(f"Got {len(raws)} results from Qdrant")

        index_messages = []
        for raw in raws:
            try:
                index_messages.append(IndexMessageModel(**raw.payload))
            except Exception:
                logger.warn("Error parsing index message", exc_info=True)

        messages = await self.store.message_get_index(index_messages)

        return SearchModel[MessageModel](
            answers=[
                SearchAnswerModel[MessageModel](data=m, score=s)
                for m, s in zip(messages, [raw.score for raw in raws])
            ],
            query=q,
            stats=SearchStatsModel(total=total, time=time.monotonic() - start),
        )

    async def message_index(self, message: StoredMessageModel, user_id: UUID) -> None:
        logger.debug(f'Indexing message "{message.id}"')
        self._loop.create_task(self._index_background(message, user_id))

    async def _index_background(
        self, message: StoredMessageModel, user_id: UUID
    ) -> None:
        logger.debug(f"Starting indexing worker for message: {message.id}")

        vector = await openai.vector_from_text(message.content, user_id)
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
