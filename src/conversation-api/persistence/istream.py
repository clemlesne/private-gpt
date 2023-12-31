from abc import ABC, abstractmethod
from enum import Enum
from models.readiness import ReadinessStatus
from typing import AsyncGenerator, Callable, Literal, Any
from uuid import UUID


class StreamImplementation(str, Enum):
    REDIS = "redis"


class IStream(ABC):
    STOPWORD: str = "STOP"

    @abstractmethod
    async def readiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def push(self, content: str, token: UUID) -> None:
        pass

    def end(self, token: UUID) -> None:
        self.push(self.STOPWORD, token)

    @abstractmethod
    async def get(
        self, token: UUID, loop_func: Callable[[], bool]
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def clean(self, token: UUID) -> None:
        pass
