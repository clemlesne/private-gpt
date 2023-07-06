# Init environment variables
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Import modules
from fastapi import HTTPException, status
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_random_exponential
from tiktoken import encoding_for_model
from typing import Dict, Optional, TypeVar, Union, Hashable
from uuid import UUID
import jwt
import logging
import mmh3
import os
import tomllib


###
# Init misc
###

VERSION = os.environ.get("VERSION")

###
# Init config
###

T = TypeVar("T")


class ConfigNotFound(Exception):
    pass


def get_config(
    section: Optional[str],
    key: str,
    validate: T,
    default: T = None,
    required: bool = False,
) -> T:
    """
    Get config from environment variable or config file.
    """

    def get_env(key: str, res_default: T) -> Union[str, T]:
        """
        Get config from environment variable.
        """
        key = f"pg_{key}".upper()
        return os.environ.get(key, res_default)

    # Get config from file
    res = None
    if section:
        res = CONFIG.get(section, {}).get(key, get_env(f"{section}_{key}", default))
    else:
        res = CONFIG.get(key, get_env(key, default))

    # Check if required
    if required and not res:
        raise ConfigNotFound(f'Cannot find config "{section}/{key}"')

    # Convert to res_type
    try:
        if validate is bool:
            res = res.strip().lower() == "true"
        elif validate is int:
            res = int(res)
        elif validate is float:
            res = float(res)
        elif validate is UUID:
            res = UUID(res)
    except Exception:
        raise ConfigNotFound(
            f'Cannot convert config "{section}/{key}" ({validate.__name__}), found "{res}" ({type(res).__name__})'
        )

    # Check res type
    if not isinstance(res, validate):
        raise ConfigNotFound(
            f'Cannot validate config "{section}/{key}" ({validate.__name__}), found "{res}" ({type(res).__name__})'
        )

    return res


CONFIG_FILE = "config.toml"
CONFIG_FOLDER = Path(os.environ.get("PG_CONFIG_PATH", ".")).absolute()
CONFIG_PATH = None
CONFIG = None
while CONFIG_FOLDER:
    CONFIG_PATH = f"{CONFIG_FOLDER}/{CONFIG_FILE}"
    print(f'Try to load config "{CONFIG_PATH}"')
    try:
        with open(CONFIG_PATH, "rb") as file:
            CONFIG = tomllib.load(file)
        break
    except FileNotFoundError:
        if CONFIG_FOLDER.parent == CONFIG_FOLDER:
            raise ConfigNotFound("Cannot find config file")
        CONFIG_FOLDER = CONFIG_FOLDER.parent.parent
    except tomllib.TOMLDecodeError as e:
        print(f'Cannot load config file "{CONFIG_PATH}"')
        raise e
print(f'Config "{CONFIG_PATH}" loaded')

###
# Init logging
###


def build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOGGING_APP_LEVEL)
    return logger


LOGGING_SYS_LEVEL = get_config("logging", "sys_level", str, "WARN")
logging.basicConfig(level=LOGGING_SYS_LEVEL)
LOGGING_APP_LEVEL = get_config("logging", "app_level", str, "INFO")
logger = build_logger(__name__)

###
# Init OIDC
###

OIDC_ALGORITHMS = get_config("oidc", "algorithms", list, required=True)
OIDC_API_AUDIENCE = get_config("oidc", "api_audience", str, required=True)
OIDC_ISSUERS = get_config("oidc", "issuers", list, required=True)
OIDC_JWKS = get_config("oidc", "jwks", str, required=True)


def oai_tokens_nb(content: str, encoding_name: str) -> int:
    encoding = encoding_for_model(encoding_name)
    return len(encoding.encode(content))


def hash_token(str: Union[str, Hashable]) -> UUID:
    return UUID(bytes=mmh3.hash_bytes(str))


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

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=0.5, max=30))
    def _load_jwks(self) -> None:
        logging.debug("Loading signing key from JWT")
        self.signing_key = self.jwks_client.get_signing_key_from_jwt(self.token)
