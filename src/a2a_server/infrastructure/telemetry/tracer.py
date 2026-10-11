from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from src.a2a_server.infrastructure.middleware.middleware import FilteringSpanExporter

def setup_tracer(APP_NAME: str,
                 OTEL_EXPORTER_OTLP_ENDPOINT: str) -> None:

    # Create a TracerProvider
    resource = Resource.create({
                    "service.name": APP_NAME
    })

    trace_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(trace_provider)

    # # Configure OTLP exporter and export spans via grpc
    otlp_exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, 
        insecure=True
    )

    # Wrap the exporter with our filtering exporter
    filtering_exporter = FilteringSpanExporter(otlp_exporter)

    # Add processor with filtered exporter
    trace_provider.add_span_processor(BatchSpanProcessor(filtering_exporter))

    # Optional: metrics (disabled if not needed)
    metrics.set_meter_provider(MeterProvider(resource=resource))

    # Instrument aiohttp and logging
    AioHttpClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    # create trace
    tracer = trace.get_tracer(APP_NAME)
    return tracer