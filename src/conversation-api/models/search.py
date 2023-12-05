from pydantic import BaseModel
from typing import List, TypeVar, Generic


T = TypeVar("T", bound=BaseModel)


class SearchAnswerModel(BaseModel, Generic[T]):
    data: T
    score: float


class SearchStatsModel(BaseModel):
    time: float
    total: int


class SearchModel(BaseModel, Generic[T]):
    answers: List[SearchAnswerModel[T]]
    query: str
    stats: SearchStatsModel
