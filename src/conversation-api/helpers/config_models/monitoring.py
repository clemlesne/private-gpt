from enum import Enum
from pydantic import BaseModel, SecretStr


class LoggingLevel(str, Enum):
    # Copied from https://docs.python.org/3.11/library/logging.html#logging-levels
    CRITICAL = "CRITICAL"
    DEBUG = "DEBUG"
    ERROR = "ERROR"
    INFO = "INFO"
    WARN = "WARN"  # Alias for WARNING, non-standard but used by the logging module
    WARNING = "WARNING"


class LoggingMonitoringModel(BaseModel):
    app_level: LoggingLevel = LoggingLevel.INFO
    sys_level: LoggingLevel = LoggingLevel.WARNING


class AzureAppInsightsModel(BaseModel):
    connection_str: SecretStr


class MonitoringModel(BaseModel):
    logging: LoggingMonitoringModel
    azure_app_insights: AzureAppInsightsModel
