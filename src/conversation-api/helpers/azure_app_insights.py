from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from helpers.config import CONFIG
from logging import Logger
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggingHandler


AZ_CREDENTIAL = DefaultAzureCredential()
APPINSIGHTS_CONNECTION_STR = (
    CONFIG.monitoring.azure_app_insights.connection_str.get_secret_value()
)


def strip_query_params(url: str) -> str:
    return url.split("?")[0]


def init():
    # Logs
    set_logger_provider(LoggerProvider())
    log_exporter = AzureMonitorLogExporter(
        connection_string=APPINSIGHTS_CONNECTION_STR, credential=AZ_CREDENTIAL
    )
    get_logger_provider().add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )

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


def trace_logger(logger: Logger):
    handler = LoggingHandler()
    logger.addHandler(handler)
