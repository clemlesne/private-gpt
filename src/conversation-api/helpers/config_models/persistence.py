from enum import Enum
from persistence.icache import CacheImplementation
from persistence.isearch import SearchImplementation
from persistence.istore import StoreImplementation
from persistence.istream import StreamImplementation
from pydantic import BaseModel, HttpUrl, SecretStr
from typing import Optional, TypeVar, Generic, Union


ConfigType = TypeVar("ConfigType", bound=BaseModel)
ImplementationType = TypeVar("ImplementationType", bound=Enum)


class ConfigModel(BaseModel, Generic[ImplementationType, ConfigType]):
    config: ConfigType
    type: ImplementationType


class QdrantModel(BaseModel):
    collection: str = "messages"
    host: str
    https: bool = False
    port: int = 6333
    prefer_grpc: bool = True


class RedisModel(BaseModel):
    db: int = 0
    host: str
    password: Optional[SecretStr] = None
    port: int = 6379
    ssl: bool = False
    username: Optional[str] = None


class CosmosModel(BaseModel):
    consistency: Optional[str] = None
    database: str
    url: HttpUrl


class PersistenceModel(BaseModel):
    cache: ConfigModel[CacheImplementation, RedisModel]
    search: ConfigModel[SearchImplementation, QdrantModel]
    store: ConfigModel[StoreImplementation, Union[CosmosModel, RedisModel]]
    stream: ConfigModel[StreamImplementation, RedisModel]
