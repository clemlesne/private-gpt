from helpers.config_models.persistence import RedisModel
from helpers.logging import build_logger
from models.readiness import ReadinessStatus
from persistence.icache import ICache
from persistence.istream import IStream
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.backoff import ExponentialBackoff
from redis.exceptions import BusyLoadingError, ConnectionError, TimeoutError
from redis.retry import Retry
from uuid import UUID, uuid4
import asyncio
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)


_logger = build_logger(__name__)
CACHE_TTL_SECS = 60 * 60 * 24 * 7  # 1 week


def _config(config: RedisModel) -> Dict[str, Any]:
    return {
        "db": config.db,
        "host": config.host,
        "password": config.password.get_secret_value() if config.password else None,
        "port": config.port,
        "retry_on_error": [BusyLoadingError, ConnectionError, TimeoutError],
        "retry": Retry(ExponentialBackoff(), 3),
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
        "ssl": config.ssl,
        "username": config.username,
    }


async def _readiness(aclient: AsyncRedis) -> ReadinessStatus:
    try:
        tmp_id = str(uuid4())
        await aclient.set(tmp_id, "dummy")
        await aclient.get(tmp_id)
        await aclient.delete(tmp_id)
    except Exception:
        _logger.warn("Error connecting to Redis", exc_info=True)
        return ReadinessStatus.FAIL
    return ReadinessStatus.OK


class RedisStream(IStream):
    _PREFIX: str = "stream"

    def __init__(self, config: RedisModel):
        self._client = Redis(**_config(config))
        self._aclient = AsyncRedis(**_config(config))

    async def areadiness(self) -> ReadinessStatus:
        return await _readiness(self._aclient)

    def push(self, content: str, token: UUID) -> None:
        self._client.xadd(self._key(token), {"message": content})

    async def aget(
        self, token: UUID, loop_func: Callable[[], Awaitable[bool]]
    ) -> AsyncGenerator[str, None]:
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
            messages_raw = await self._aclient.xread(
                block=10_000,  # Wait 10 seconds
                streams={message_key: stream_id},
            )

            if not messages_raw:
                break

            for message_content in messages_raw[0][1]:
                stream_id = message_content[0]
                message = message_content[1][b"message"].decode("utf-8")
                if message == self.STOPWORD:
                    is_end = True
                    break
                yield message

            # 8 messages per second, enough for give a good user experience, but not too much for not using the thread too much
            await asyncio.sleep(0.125)

        # Send the end of stream message
        yield self.STOPWORD

    async def aclean(self, token: UUID) -> None:
        await self._aclient.delete(self._key(token))

    def _key(self, token: UUID) -> str:
        return f"{self._PREFIX}:{token.hex}"


class RedisCache(ICache):
    def __init__(self, config: RedisModel):
        self._client = Redis(**_config(config))
        self._aclient = AsyncRedis(**_config(config))

    async def areadiness(self) -> ReadinessStatus:
        return await _readiness(self._aclient)

    def exists(self, key: str) -> bool:
        return self._client.exists(key) != 0

    async def aexists(self, key: str) -> bool:
        return await self._aclient.exists(key) != 0

    def get(self, key: str) -> Optional[str]:
        raw = self._client.get(key)
        if raw is None:
            return None
        return raw.decode("utf-8")

    async def aget(self, key: str) -> Optional[str]:
        raw = await self._aclient.get(key)
        if raw is None:
            return None
        return raw.decode("utf-8")

    def set(self, key: str, value: str, expiry: Optional[int] = None) -> None:
        self._client.set(key, value, ex=(expiry or CACHE_TTL_SECS))

    async def aset(self, key: str, value: str, expiry: Optional[int] = None) -> None:
        await self._aclient.set(key, value, ex=(expiry or CACHE_TTL_SECS))

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def hget(self, key: str) -> Optional[Dict[str, str]]:
        raw = self._client.hgetall(key)
        if not raw:
            return None
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in raw.items()}

    def hset(
        self, key: str, mapping: Dict[str, str], expiry: Optional[int] = None
    ) -> None:
        if not mapping:
            return
        self._client.hset(key, mapping=mapping)
        # TTL is not supported by hset, so we need to set it manually (https://github.com/redis/redis/issues/167#issuecomment-427708753)
        self._client.expire(key, (expiry or CACHE_TTL_SECS))

    def mget(self, keys: Union[str, List[str]]) -> Dict[str, Optional[str]]:
        raws = self._client.mget(keys)
        if not raws:
            return {}
        return {
            keys[i]: (raw.decode("utf-8") if raw else None)
            for i, raw in enumerate(raws)
        }

    def mset(self, mapping: Dict[str, str], expiry: Optional[int] = None) -> None:
        self._client.mset(mapping)
        # TTL is not supported by hset, so we need to set it manually (https://github.com/redis/redis/issues/167#issuecomment-427708753)
        for key in mapping.keys():
            self._client.expire(key, (expiry or CACHE_TTL_SECS))
