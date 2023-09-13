# Init environment variables
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Import modules
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from enum import Enum
from fastapi import HTTPException, status
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from uuid import UUID
import html
import json
import jwt
import logging
import mmh3
import os
import re
import tomllib


###
# Init misc
###

VERSION: str = os.environ.get("VERSION") or "0.0.0-unknown"
AZ_CREDENTIAL: DefaultAzureCredential = DefaultAzureCredential()

###
# Init config
###

T = TypeVar("T", bool, int, float, UUID, str, Enum, list, None)


class ConfigNotFound(Exception):
    pass


def get_config(
    sections: Optional[Union[str, list[str]]],
    key: str,
    validate: Type[T],
    default: Any = None,
    required: bool = False,
) -> T:
    """
    Get config from environment variable or config file.
    """

    def get_env(key: Union[str, list[str]], res_default: T) -> T:
        """
        Get config from environment variable.
        """
        if isinstance(key, list):
            key = "_".join(key)
        key = f"pg_{key}".upper()
        res = os.environ.get(key, res_default)
        try:
            return json.loads(str(res))
        except json.JSONDecodeError:
            return res or res_default

    # Get config from file
    res = None
    if sections:
        if isinstance(sections, list):
            res = CONFIG
            for section in sections:
                res = res.get(section, {})
        else:
            res = CONFIG.get(sections, {})
        res = res.get(key, get_env(f"{sections}_{key}", default))
    else:
        res = CONFIG.get(key, get_env(key, default))

    # Check if required
    if required and not res:
        raise ConfigNotFound(f'Cannot find config "{sections}/{key}"')

    # Convert to res_type
    try:
        if validate is str:  # str
            pass  # no conversion needed
        elif validate is bool:  # bool
            res = res.strip().lower() == "true"
        elif validate is int:  # int
            res = int(res)
        elif validate is float:  # float
            res = float(res)
        elif validate is UUID:  # UUID
            res = UUID(res)
        elif issubclass(validate, Enum):  # Enum
            res = validate(res)
    except (ValueError, TypeError, AttributeError):
        raise ConfigNotFound(
            f'Cannot convert config "{sections}/{key}" ({validate.__name__}), found "{res}" ({type(res).__name__})'
        )

    # Check res type
    if not isinstance(res, validate):
        raise ConfigNotFound(
            f'Cannot validate config "{sections}/{key}" ({validate.__name__}), found "{res}" ({type(res).__name__})'
        )

    return res


CONFIG_FILE = "config.toml"
CONFIG_FOLDER = Path(os.environ.get("PG_CONFIG_PATH", ".")).absolute()
CONFIG_PATH: Union[str, None] = None
CONFIG: Dict[str, Any] = {}
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
    except Exception as e:
        print(f'Cannot load config file "{CONFIG_PATH}"')
        raise e
print(f'Config "{CONFIG_PATH}" loaded')

###
# Init Azure App Insights
###


def strip_query_params(url: str) -> str:
    return url.split("?")[0]


APPINSIGHTS_CONNECTION_STR = get_config(
    ["monitoring", "azure_app_insights"], "connection_str", str, required=True
)
# Logs
set_logger_provider(LoggerProvider())
log_exporter = AzureMonitorLogExporter(
    connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL
)
get_logger_provider().add_log_record_processor(BatchLogRecordProcessor(log_exporter))
# Metrics
metric_exporter = AzureMonitorMetricExporter(
    connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL
)
# Traces
# TODO: Enable sampling
RedisInstrumentor().instrument()  # Redis
RequestsInstrumentor().instrument()  # Requests
SystemMetricsInstrumentor().instrument()  # System
URLLib3Instrumentor().instrument(url_filter=strip_query_params)  # Urllib3
trace.set_tracer_provider(TracerProvider())
trace_exporter = AzureMonitorTraceExporter(
    connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL
)
span_processor = BatchSpanProcessor(trace_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

###
# Init logging
###


def build_logger(name: str) -> logging.Logger:
    handler = LoggingHandler()
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(LOGGING_APP_LEVEL)
    return logger


LOGGING_SYS_LEVEL = get_config(["monitoring", "logging"], "sys_level", str, "WARN")
logging.basicConfig(level=LOGGING_SYS_LEVEL)
LOGGING_APP_LEVEL = get_config(["monitoring", "logging"], "app_level", str, "INFO")
_logger = build_logger(__name__)

###
# Init OIDC
###

OIDC_ALGORITHMS: List[str] = get_config("oidc", "algorithms", list, required=True)
OIDC_API_AUDIENCE = get_config("oidc", "api_audience", str, required=True)
OIDC_ISSUERS: List[str] = get_config("oidc", "issuers", list, required=True)
OIDC_JWKS = get_config("oidc", "jwks", str, required=True)


def sanitize(raw: Optional[str]) -> Optional[str]:
    """
    Takes a raw string of HTML and removes all HTML tags, Markdown tables, and line returns.
    """
    if not raw:
        return None

    # Remove HTML doctype
    raw = re.sub(r"<!DOCTYPE[^>]*>", " ", raw)
    # Remove HTML head
    raw = re.sub(r"<head\b[^>]*>[\s\S]*<\/head>", " ", raw)
    # Remove HTML scripts
    raw = re.sub(r"<script\b[^>]*>[\s\S]*?<\/script>", " ", raw)
    # Remove HTML styles
    raw = re.sub(r"<style\b[^>]*>[\s\S]*?<\/style>", " ", raw)
    # Extract href from HTML links, in the form of "(href) text"
    raw = re.sub(r"<a\b[^>]*href=\"([^\"]*)\"[^>]*>([^<]*)<\/a>", r"(\1) \2", raw)
    # Remove HTML tags
    raw = re.sub(r"<[^>]*>", " ", raw)
    # Remove Markdown tables
    raw = re.sub(r"[-|]{2,}", " ", raw)
    # Remove Markdown code blocks
    raw = re.sub(r"```[\s\S]*```", " ", raw)
    # Remove Markdown bold, italic, strikethrough, code, heading, table delimiters, links, images, comments, and horizontal rules
    raw = re.sub(r"[*_`~#|!\[\]<>-]+", " ", raw)
    # Remove line returns, tabs and spaces
    raw = re.sub(r"[\n\t\v ]+", " ", raw)
    # Remove HTML entities
    raw = html.unescape(raw)
    # Remove leading and trailing spaces
    raw = raw.strip()

    return raw


def try_or_none(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


def hash_token(str: Union[str, bytes, bytearray, memoryview]) -> UUID:
    return UUID(bytes=mmh3.hash_bytes(str))


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
