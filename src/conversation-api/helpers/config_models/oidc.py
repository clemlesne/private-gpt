from pydantic import BaseModel
from typing import List


class OidcModel(BaseModel):
    algorithms: List[str]
    api_audience: str
    issuers: List[str]
    jwks: str
