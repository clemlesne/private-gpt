# Init environment variables
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Import modules
from fastapi import HTTPException, status
from tenacity import retry, stop_after_attempt
from typing import Dict
import jwt
import logging
import os


###
# Init misc
###

VERSION = os.environ.get("VERSION")

###
# Init logging
###

LOGGING_SYS_LEVEL = os.environ.get("MS_LOGGING_SYS_LEVEL", logging.WARN)
logging.basicConfig(level=LOGGING_SYS_LEVEL)
LOGGING_APP_LEVEL = os.environ.get("MS_LOGGING_APP_LEVEL", logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_APP_LEVEL)

###
# Init OIDC
###

OIDC_API_AUDIENCE = os.environ.get("MS_OIDC_API_AUDIENCE")
OIDC_JWKS = os.environ.get("MS_OIDC_JWKS")
OIDC_AUTHORITY = os.environ.get("MS_OIDC_AUTHORITY")
OIDC_ALGORITHMS = os.environ.get("MS_OIDC_ALGORITHMS", "").split(",")


class VerifyToken:
    def __init__(self, token):
        self.token = token
        self.jwks_client = jwt.PyJWKClient(OIDC_JWKS)


    def verify(self) -> Dict[str, str]:
        try:
            self._load_jwks()
        except Exception:
            logger.error("Cannot load signing key from JWT", exc_info=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            payload = jwt.decode(
                self.token,
                algorithms=OIDC_ALGORITHMS,
                audience=OIDC_API_AUDIENCE,
                issuer=OIDC_AUTHORITY,
                key=self.signing_key.key,
                options={"require": ["exp", "iss", "sub"]},
            )
        except Exception:
            logger.info("JWT token is invalid", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token is invalid",
            )

        return payload


    @retry(stop=stop_after_attempt(3))
    def _load_jwks(self) -> None:
        self.signing_key = self.jwks_client.get_signing_key_from_jwt(self.token)
