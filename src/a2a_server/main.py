import os
import sys

import logging
import time
import uvicorn

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.a2a_server.infrastructure.telemetry.metric import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    A2A_MESSAGES_TOTAL,
    A2A_ROUTER_ERRORS_TOTAL,
    IN_FLIGHT_REQUESTS
)

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    AuthorizationDeniedError,
)

from src.a2a_server.common.exceptions.a2a_error import (
    A2ARequestError,
    A2ARouterError,
)

from src.a2a_server.a2a.message_model import A2ARequest, A2AEnvelope, A2AResponse
from src.a2a_server.a2a.server import A2AServer
from src.a2a_server.application.orchestration.orchestrator import Orchestrator
from src.a2a_server.infrastructure.telemetry.tracer import setup_tracer
from src.a2a_server.a2a.agent_card import AGENT_CARD as agent
from src.a2a_server.infrastructure.middleware.middleware import RequestContextMiddleware

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

from src.a2a_server.config.logger import setup_logger
from src.a2a_server.config.settings import settings

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

# Setup logging
setup_logger(settings.LOG_LEVEL, 
             settings.APP_NAME, 
             settings.OTEL_STDOUT_LOG_GROUP, 
             settings.LOG_GROUP)

logger = logging.getLogger(__name__)
    
# Setup OpenTelemetry tracer
setup_tracer(settings.APP_NAME, 
             settings.OTEL_EXPORTER_OTLP_ENDPOINT)

tracer = trace.get_tracer(__name__)

# ---------------------------------
# Lifespan (startup/shutdown)
# ---------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("func.lifespan()")
    logger.info(" **** Starting up the application...")
    yield
    logger.info(" **** Shutting down the application...")
    logger.info(" **** Closing resources (5 seconds)...")
    time.sleep(1)
    logger.info(" **** Resources Closed...")
    logger.info(" **** Shutting down complete, bye ...")
    
# ---------------------------------
# Create FastAPI instance
# ---------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Add TrustedHostMiddleware to the FastAPI application
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["py-inventory-a2a-v2",
                   "localhost",
                   "127.0.0.1",
                    "prometheus",
                   "host.docker.internal",
                   "*.a2a-v2"]
)

# Add middleware to the FastAPI application
app.add_middleware(RequestContextMiddleware)

# ---------------------------------
# Exception Handlers (standardized error responses)
# ---------------------------------
@app.exception_handler(InvalidAccessTokenError)
async def invalid_access_token_exception_handler(request: Request, exc: InvalidAccessTokenError):
    """Handle invalid access token exceptions with standardized 401 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Invalid access token error: {exc.message}")
    
    error_response = exc.to_dict()
    
    return JSONResponse(
        status_code=exc.status_code or 401,
        content=error_response,
        headers={"x-request-id": request_id}
    )

@app.exception_handler(AuthorizationDeniedError)
async def authorization_denied_exception_handler(request: Request, exc: AuthorizationDeniedError):
    """Handle authorization denied exceptions with standardized 403 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Authorization denied: {exc.message}")
    
    error_response = exc.to_dict()
    
    return JSONResponse(
        status_code=exc.status_code or 403,
        content=error_response,
        headers={"x-request-id": request_id}
    )

# ---------------------------------
# Helper Functions
def create_a2a_error_response(
    exception: Exception,
    error_type: str,
    request_envelope: A2AEnvelope,
    a2aRequest: A2ARequest,
    span: trace.Span
) -> A2AResponse:
    """Create a standardized A2A error response envelope.
    
    Args:
        exception: The exception that occurred
        error_type: String identifier for the error type (e.g., 'A2ARouterError', 'Exception')
        request_envelope: The original A2A request envelope to extract target_agent
        a2aRequest: The original A2A request object
        
    Returns:
        A2AResponse: Formatted error response ready to return to client
    """
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))
            
    error_envelope = A2AEnvelope(
        source_agent="a2a-server",
        target_agent=request_envelope.source_agent,
        message_type="error",
        payload={"error": str(exception), "error_type": error_type}
    )
    return A2AResponse.create(domain_envelope=error_envelope, a2aRequest=a2aRequest)

# ---------------------------------
# Application Metadata
# ---------------------------------
orchestrator = Orchestrator()
a2AServer = A2AServer(settings, orchestrator)

# ---------------------------------
# API Endpoints
# ---------------------------------
@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/health")
def health():
    return Response(
        content='{"status": "OK"}',
        media_type="application/json"
    )
    
@app.get("/v1/info")
def get_info():
    with tracer.start_as_current_span("controller.get_info"):
        """Get application settings information."""
        logger.info("func.get_info()")

        return settings

@app.get("/.well-known/agent-card.json")
def agent_card():
    with tracer.start_as_current_span("controller.get_agent_card") as span:
        """Get application agent card information."""
        logger.info("func.get_agent_card()")
        
        return agent

@app.post("/a2a/message")
async def a2a_message(a2aRequest: A2ARequest, request: Request) -> A2AResponse:
    with tracer.start_as_current_span("main.a2a_message") as span:
        logger.info("func.a2a_message()")
        
        start = time.time()
        IN_FLIGHT_REQUESTS.inc() 
                  
        try:
            request_envelope: A2AEnvelope = a2aRequest.parse_domain_envelope()
            
            A2A_MESSAGES_TOTAL.labels(message_type=request_envelope.message_type).inc()   
                        
            response = await a2AServer.router(request_envelope)
            response_envelope: A2AResponse = A2AResponse.create(domain_envelope=response, a2aRequest=a2aRequest)
            
            span.set_status(Status(StatusCode.OK)) 
            return response_envelope
        
        except A2ARouterError as e:
            logger.error("Error A2ARouterError message", exc_info=e)
            A2A_ROUTER_ERRORS_TOTAL.inc()
            return create_a2a_error_response(e, "A2ARouterError", request_envelope, a2aRequest, span)
        
        except A2ARequestError as e:
            logger.error("Error A2ARequestError message", exc_info=e)
            return create_a2a_error_response(e, "Exception", request_envelope, a2aRequest, span)
        
        except Exception as e:
            logger.error("Error uncaught Exception", exc_info=e)
            return create_a2a_error_response(e, "Exception", request_envelope, a2aRequest, span)
        
        finally:
            HTTP_REQUEST_DURATION_SECONDS.labels(method="POST",endpoint="/a2a/message").observe(time.time() - start)
            IN_FLIGHT_REQUESTS.dec()

# Server entrypoint function
def run():
    """Server entrypoint execution handler."""
    try:
        logger.info(f"SERVER: {settings.HOST}:{settings.PORT}")
        
        uvicorn.run(app, 
                    host=settings.HOST, 
                    port=int(settings.PORT))
        
    except Exception as e:
        logger.error(f"Server encountered an error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped SUCCESSFULLY.")
        
# Run the server if this script is executed directly
if __name__ == "__main__":
    run()