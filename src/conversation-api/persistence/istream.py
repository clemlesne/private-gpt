from abc import ABC, abstractmethod
from enum import Enum
from models.readiness import ReadinessStatus
from typing import AsyncGenerator, Callable
from uuid import UUID


class StreamImplementation(str, Enum):
    REDIS = "redis"


class IStream(ABC):
    STOPWORD: str = "STOP"

    @abstractmethod
    async def areadiness(self) -> ReadinessStatus:
        pass

    @abstractmethod
    def push(self, content: str, token: UUID) -> None:
        pass

    def end(self, token: UUID) -> None:
        self.push(self.STOPWORD, token)

    @abstractmethod
    async def aget(
        self, token: UUID, loop_func: Callable[[], bool]
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def aclean(self, token: UUID) -> None:
        pass
