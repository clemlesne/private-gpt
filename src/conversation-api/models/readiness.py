from enum import Enum
from pydantic import BaseModel
from typing import List


class ReadinessStatus(str, Enum):
    FAIL = "fail"
    OK = "ok"


class ReadinessCheckModel(BaseModel):
    id: str
    status: ReadinessStatus

    class Config:
        use_enum_values = True


class ReadinessModel(BaseModel):
    checks: List[ReadinessCheckModel]
    status: str
