# Init environment variables
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Import modules
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter, AzureMonitorMetricExporter, AzureMonitorTraceExporter
from fastapi import HTTPException, status
from opentelemetry import trace
from opentelemetry._logs import (get_logger_provider, set_logger_provider)
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import (LoggerProvider, LoggingHandler)
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
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
AZ_CREDENTIAL = DefaultAzureCredential()

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
        if validate is bool: # bool
            res = res.strip().lower() == "true"
        elif validate is int: # int
            res = int(res)
        elif validate is float: # float
            res = float(res)
        elif validate is UUID: # UUID
            res = UUID(res)
        else: # Enum
            try:
                res = validate(res)
            except Exception:
                pass
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
# Init Azure App Insights
###

def strip_query_params(url: str) -> str:
    return url.split("?")[0]

APPINSIGHTS_CONNECTION_STR = get_config("appinsights", "connection_str", str, required=True)
# Logs
set_logger_provider(LoggerProvider())
log_exporter = AzureMonitorLogExporter(connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL)
get_logger_provider().add_log_record_processor(BatchLogRecordProcessor(log_exporter))
# Metrics
metric_exporter = AzureMonitorMetricExporter(connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL)
# Traces
# TODO: Enable sampling
set_meter_provider(MeterProvider([PeriodicExportingMetricReader(ConsoleMetricExporter())]))
SystemMetricsInstrumentor().instrument() # System
RedisInstrumentor().instrument() # Redis
RequestsInstrumentor().instrument() # Requests
URLLib3Instrumentor().instrument(url_filter=strip_query_params) # Urllib3
trace.set_tracer_provider(TracerProvider())
trace_exporter = AzureMonitorTraceExporter(connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL)
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

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    def _load_jwks(self) -> None:
        logging.debug("Loading signing key from JWT")
        self.signing_key = self.jwks_client.get_signing_key_from_jwt(self.token)
