# Import utils
from utils import build_logger, get_config

# Import misc
from .icache import ICache
from .istream import IStream
from models.readiness import ReadinessStatus
from redis import Redis
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Union,
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
    CACHE_TTL_SECS = 60 * 60  # 1 hour

    async def readiness(self) -> ReadinessStatus:
        return await _readiness()

    def exists(self, key: str) -> bool:
        return client.exists(key) != 0

    def get(self, key: str) -> Optional[str]:
        raw = client.get(key)
        if raw is None:
            return None
        return raw.decode("utf-8")

    def set(self, key: str, value: str, expiry: Optional[int] = None) -> None:
        client.set(key, value, ex=(expiry or self.CACHE_TTL_SECS))

    def delete(self, key: str) -> None:
        client.delete(key)

    def hget(self, key: str) -> Optional[Dict[str, str]]:
        raw = client.hgetall(key)
        if not raw:
            return None
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in raw.items()}

    def hset(self, key: str, mapping: Dict[str, str], expiry: Optional[int] = None) -> None:
        if not mapping:
            return
        client.hset(key, mapping=mapping)
        # TTL is not supported by hset, so we need to set it manually (https://github.com/redis/redis/issues/167#issuecomment-427708753)
        client.expire(key, (expiry or self.CACHE_TTL_SECS))

    def mget(self, keys: Union[str, List[str]]) -> Dict[str, Optional[str]]:
        raws = client.mget(keys)
        if not raws:
            return {}
        return {keys[i]: (raw.decode("utf-8") if raw else None) for i, raw in enumerate(raws)}

    def mset(self, mapping: Dict[str, str], expiry: Optional[int] = None) -> None:
        client.mset(mapping)
        # TTL is not supported by hset, so we need to set it manually (https://github.com/redis/redis/issues/167#issuecomment-427708753)
        for key in mapping.keys():
            client.expire(key, (expiry or self.CACHE_TTL_SECS))
