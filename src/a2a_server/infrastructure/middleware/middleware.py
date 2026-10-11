import logging
import uuid

from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from src.a2a_server.config.logger import REQUEST_ID_CTX

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.a2a_server.domain.dto.context import SecurityContext
from src.a2a_server.infrastructure.context.request_context import (
    set_security_context,
    reset_security_context,
)

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

TRACING_EXCLUDED_PATHS = ["/metrics", "/health", "/readiness"]

class FilteringSpanExporter(SpanExporter):
    """Filters out spans from excluded paths before export"""
    
    def __init__(self, delegate_exporter):
        self.delegate_exporter = delegate_exporter
    
    def export(self, spans):
        # Filter spans - only export spans that are not from excluded paths
        filtered_spans = []
        
        for span in spans:
            attributes = span.attributes or {}
            http_target = attributes.get("http.target", "")
            http_url = attributes.get("http.url", "")
            
            # Check if this span should be excluded
            should_exclude = False
            for path in TRACING_EXCLUDED_PATHS:
                if http_target.startswith(path) or path in http_url:
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_spans.append(span)
        
        # Export only non-excluded spans
        if filtered_spans:
            return self.delegate_exporter.export(filtered_spans)
        return SpanExportResult.SUCCESS
    
    def shutdown(self):
        self.delegate_exporter.shutdown()
    
    def force_flush(self, timeout_millis=30000):
        return self.delegate_exporter.force_flush(timeout_millis)
    
class RequestContextMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app):
        super().__init__(app)
        logger.info("Initializing Middleware SUCCESSFULLY")

    async def dispatch(self, request: Request, call_next):

        # Skip tracing for excluded paths
        if request.url.path in TRACING_EXCLUDED_PATHS:
            return await call_next(request)
                
        span_name = f"middleware:{request.url.path}"
        with tracer.start_as_current_span(span_name):
            logger.info(f"Processing request: {request}")
            
            request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
            auth_header = request.headers.get("Authorization")
            
            auth_token = None
            if auth_header and auth_header.startswith("Bearer "):
                auth_token = auth_header.split(" ", 1)[1]
            
            logger.info(f"Setting Request ID {request_id} and auth_token in context: {auth_token}")
            
            REQUEST_ID_CTX.set(request_id)
            
            sec_context = SecurityContext(
                x_request_id=request_id,
                auth_token=auth_token,
            )
            
            token = set_security_context(sec_context)
            
            try:
                response = await call_next(request)
                response.headers["x-request-id"] = request_id
                
                return response
            finally:
                reset_security_context(token)
