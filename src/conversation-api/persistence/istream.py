from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncGenerator, Callable, Literal, Any
from uuid import UUID


class StreamImplementation(str, Enum):
    REDIS = "redis"


class IStream(ABC):
    @abstractmethod
    def push(self, content: str, token: UUID) -> None:
        pass

    @abstractmethod
    async def get(
        self, token: UUID, loop_func: Callable[[], bool]
    ) -> AsyncGenerator[Any | Literal["STOP"], None]:
        pass

    @abstractmethod
    def clean(self, token: UUID) -> None:
        pass
