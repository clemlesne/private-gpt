from pydantic import BaseModel
from pydantic.generics import GenericModel
from typing import List, TypeVar, Generic


T = TypeVar("T", bound=BaseModel)


class SearchAnswerModel(GenericModel, Generic[T]):
    data: T
    score: float


class SearchStatsModel(BaseModel):
    time: float
    total: int


class SearchModel(GenericModel, Generic[T]):
    answers: List[SearchAnswerModel[T]]
    query: str
    stats: SearchStatsModel
