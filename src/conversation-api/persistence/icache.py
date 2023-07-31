from abc import ABC, abstractmethod
from enum import Enum
from uuid import UUID
from models.readiness import ReadinessStatus
from typing import Dict, List, Optional, Union


class CacheImplementation(str, Enum):
    REDIS = "redis"


class ICache(ABC):
    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set(self, key: str, value: str, expiry: Optional[int] = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def hget(self, key: str) -> Optional[Dict[str, Optional[str]]]:
        pass

    @abstractmethod
    def hset(
        self, key: str, mapping: Dict[str, str], expiry: Optional[int] = None
    ) -> None:
        pass

    @abstractmethod
    def mget(self, keys: Union[str, List[str]]) -> Dict[str, Optional[str]]:
        pass

    @abstractmethod
    def mset(self, mapping: Dict[str, str], expiry: Optional[int] = None) -> None:
        pass
