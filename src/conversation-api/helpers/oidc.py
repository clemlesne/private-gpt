from fastapi import HTTPException, status
from helpers.config import CONFIG
from helpers.logging import build_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing import Dict, List
import jwt
import logging


_logger = build_logger(__name__)
OIDC_ALGORITHMS: List[str] = CONFIG.oidc.algorithms
OIDC_API_AUDIENCE = CONFIG.oidc.api_audience
OIDC_ISSUERS: List[str] = CONFIG.oidc.issuers
OIDC_JWKS = CONFIG.oidc.jwks


class VerifyToken:
    jwks_client = jwt.PyJWKClient(OIDC_JWKS, cache_keys=True)

    def __init__(self, token):
        self.token = token

    def verify(self) -> Dict[str, str]:
        if not self.token:
            _logger.info("JWT token is missing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token is missing",
            )

        try:
            self._load_jwks()
        except Exception:
            _logger.error("Cannot load signing key from JWT", exc_info=True)
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
                _logger.debug(f"Successfully validate JWT with issuer: {issuer}")
                break
            except Exception as e:
                _logger.debug(f"Fails validate JWT with issuer: {issuer}")
                last_error = e

        if not succeed:
            _logger.info("JWT token is invalid")
            _logger.debug(last_error)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token is invalid",
            )

        if not payload:
            _logger.error("Incoherent payload, shouldn't be None")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return payload

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    def _load_jwks(self) -> None:
        logging.debug("Loading signing key from JWT")
        self.signing_key = VerifyToken.jwks_client.get_signing_key_from_jwt(self.token)
