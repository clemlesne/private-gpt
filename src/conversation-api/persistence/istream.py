from abc import ABC, abstractmethod
from typing import AsyncGenerator, Callable, Literal
from uuid import UUID


class IStream(ABC):
    @abstractmethod
    def push(self, content: str, token: UUID) -> None:
        pass

    @abstractmethod
    async def get(self, token: UUID, loop_func: Callable[[], bool]) -> AsyncGenerator[any | Literal["STOP"], None]:
        pass

    @abstractmethod
    def clean(self, token: UUID) -> None:
        pass
