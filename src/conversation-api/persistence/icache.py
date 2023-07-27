from abc import ABC, abstractmethod
from enum import Enum
from models.readiness import ReadinessStatus
from typing import Dict, Mapping, Optional


class CacheImplementation(str, Enum):
    REDIS = "redis"


class ICache(ABC):
    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def hget(self, key: str) -> Optional[Dict[str, str]]:
        pass

    @abstractmethod
    def hset(self, key: str, mapping: Mapping[str, str]) -> None:
        pass
