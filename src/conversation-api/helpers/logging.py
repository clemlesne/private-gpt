from helpers.config import CONFIG
import logging
from helpers.azure_app_insights import (
    init as init_app_insights,
    trace_logger as trace_logger_app_insights,
)


LOGGING_APP_LEVEL = CONFIG.monitoring.logging.app_level.value
LOGGING_SYS_LEVEL = CONFIG.monitoring.logging.sys_level.value

logging.basicConfig(level=LOGGING_SYS_LEVEL)

app_insights_inited = False
try:
    init_app_insights()
    app_insights_inited = True
except Exception as e:
    print("Cannot init Azure App Insights", e)


def build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOGGING_APP_LEVEL)

    if app_insights_inited:
        trace_logger_app_insights(logger)

    return logger
