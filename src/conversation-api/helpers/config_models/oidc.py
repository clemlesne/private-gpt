from pydantic import BaseModel, HttpUrl
from typing import List


class OidcModel(BaseModel):
    algorithms: List[str]
    api_audience: str
    issuers: List[HttpUrl]
    jwks: str
