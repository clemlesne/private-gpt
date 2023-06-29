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

def build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOGGING_APP_LEVEL)
    return logger


LOGGING_SYS_LEVEL = os.environ.get("PG_LOGGING_SYS_LEVEL", logging.WARN)
logging.basicConfig(level=LOGGING_SYS_LEVEL)
LOGGING_APP_LEVEL = os.environ.get("PG_LOGGING_APP_LEVEL", logging.INFO)
logger = build_logger(__name__)

###
# Init OIDC
###

OIDC_API_AUDIENCE = os.environ.get("PG_OIDC_API_AUDIENCE")
OIDC_JWKS = os.environ.get("PG_OIDC_JWKS")
OIDC_ISSUERS = os.environ.get("PG_OIDC_ISSUERS", "").split(",")
OIDC_ALGORITHMS = os.environ.get("PG_OIDC_ALGORITHMS", "").split(",")


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

        succeed = False
        last_error = None
        payload = None
        for issuer in OIDC_ISSUERS:
            try:
                payload = jwt.decode(
                    self.token,
                    algorithms=OIDC_ALGORITHMS,
                    audience=OIDC_API_AUDIENCE,
                    issuer=issuer,
                    key=self.signing_key.key,
                    options={"require": ["exp", "iss", "sub"]},
                )
                succeed = True
                logger.debug(f"Successfully validate JWT with issuer: {issuer}")
                break
            except Exception as e:
                logger.debug(f"Fails validate JWT with issuer: {issuer}")
                last_error = e

        if not succeed:
            logger.info("JWT token is invalid", last_error)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token is invalid",
            )

        if not payload:
            logger.error("Incoherent payload, shouldn't be None")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return payload


    @retry(stop=stop_after_attempt(3))
    def _load_jwks(self) -> None:
        self.signing_key = self.jwks_client.get_signing_key_from_jwt(self.token)
