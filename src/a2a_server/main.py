import os
import sys

import logging
import time
import uvicorn

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response

from prometheus_client import start_http_server
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.a2a_server.infrastructure.telemetry.metric import (
    HTTP_REQUEST_DURATION_SECONDS,
    A2A_MESSAGES_TOTAL,
    A2A_ROUTER_ERRORS_TOTAL,
    A2A_REQUEST_ERRORS_TOTAL,
    A2A_UNCAUGHT_EXCEPTIONS_TOTAL,
    IN_FLIGHT_REQUESTS,
)

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    AuthorizationDeniedError,
    ForbiddenError,
    MissingTokenError,
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
from src.a2a_server.config.logger import REQUEST_ID_CTX

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

from src.a2a_server.config.logger import setup_logger
from src.a2a_server.config.settings import settings

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from src.a2a_server.infrastructure.oauth.cimd.client_metadata import CLIENT_METADATA
from src.a2a_server.infrastructure.oauth.jwks_metadata import JWKS_METADATA

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
    logger.info(" **** Starting up the application...")
    logger.info(f" **** Metrics server will start at {settings.METRICS_HOST}:{settings.METRICS_PORT}")
    
    start_http_server(int(settings.METRICS_PORT), addr=settings.METRICS_HOST)

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

# ---------------------------------
# Middleware
# ---------------------------------
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["py-inventory-a2a-v2",
                   "localhost",
                   "127.0.0.1",
                    "prometheus",
                   "host.docker.internal",
                   "*.a2a-v2"]
)

app.add_middleware(RequestContextMiddleware)

# ---------------------------------
# Exception Handlers (standardized error responses)
# ---------------------------------
@app.exception_handler(InvalidAccessTokenError)
async def invalid_access_token_exception_handler(request: Request, exc: InvalidAccessTokenError):
    """Handle invalid access token exceptions with standardized 401 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Invalid access token error: {exc.message}")
    
    error_response = create_error_response(exc, status_code=401)
    
    return JSONResponse(
        status_code=401,
        content=error_response,
        headers={"x-request-id": request_id}
    )

@app.exception_handler(AuthorizationDeniedError)
async def authorization_denied_exception_handler(request: Request, exc: AuthorizationDeniedError):
    """Handle authorization denied exceptions with standardized 403 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Authorization denied: {exc.message}")
    
    error_response = create_error_response(exc, status_code=403)
    
    return JSONResponse(
        status_code=403,
        content=error_response,
        headers={"x-request-id": request_id}
    )

@app.exception_handler(ForbiddenError)
async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
    """Handle forbidden exceptions with standardized 403 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Forbidden error: {exc.message}")
    
    error_response = create_error_response(exc, status_code=403)
    
    return JSONResponse(
        status_code=403,
        content=error_response,
        headers={"x-request-id": request_id}
    )

@app.exception_handler(MissingTokenError)
async def missing_token_exception_handler(request: Request, exc: MissingTokenError):
    """Handle missing token exceptions with standardized 401 response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"Missing token error: {exc.message}")
    
    error_response = create_error_response(exc, status_code=401)
    
    return JSONResponse(
        status_code=401,
        content=error_response,
        headers={"x-request-id": request_id}
    )

@app.exception_handler(A2ARouterError)
async def a2a_router_error_exception_handler(request: Request, exc: A2ARouterError):
    """Handle A2A router exceptions with standardized error response"""
    request_id = REQUEST_ID_CTX.get() or request.headers.get("x-request-id", "unknown")
    logger.error(f"A2A Router error: {exc.message if hasattr(exc, 'message') else str(exc)}")
    
    error_response = create_error_response(exc, status_code=400)
    
    return JSONResponse(
        status_code=400,
        content=error_response,
        headers={"x-request-id": request_id}
    )

# ---------------------------------
# Helper Functions
# ---------------------------------
def create_error_response(exception: Exception, status_code: int = None) -> dict:
    """Create a standardized error response payload.
    
    Args:
        exception: The exception that occurred
        status_code: HTTP status code for the response
        
    Returns:
        dict: Standardized error response with error, error_type, status_code, and message
    """
    error_type = exception.__class__.__name__
    
    # Map error types to user-friendly error messages
    error_mapping = {
        "InvalidAccessTokenError": "UNAUTHORIZED",
        "MissingTokenError": "UNAUTHORIZED",
        "AuthorizationDeniedError": "FORBIDDEN",
        "ForbiddenError": "FORBIDDEN",
    }
    
    error_label = error_mapping.get(error_type, "INTERNAL_SERVER_ERROR")
    
    # Use exception's status_code if available, otherwise use provided one
    final_status_code = status_code
    if hasattr(exception, 'status_code') and exception.status_code:
        final_status_code = exception.status_code
    
    return {
        "error": error_label,
        "error_type": error_type,
        "status_code": final_status_code,
        "message": exception.message if hasattr(exception, 'message') else str(exception)
    }

# ---------------------------------
# Application Metadata
# ---------------------------------
orchestrator = Orchestrator()
a2AServer = A2AServer(settings, orchestrator)

# ---------------------------------
# API Endpoints
# ---------------------------------
@app.get("/oauth/client-metadata.json")
def client_metadata():
    return JSONResponse(
        content=CLIENT_METADATA
    )

@app.get("/.well-known/jwks.json")
def jwks():
    with tracer.start_as_current_span("main.well-known.jwks") as span:
        jwks=JWKS_METADATA
        span.set_status(Status(StatusCode.OK)) 
        return JSONResponse(
            content=jwks
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
        
        except ForbiddenError as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.warning("Forbidden error in main.a2a_message", exc_info=e)
            raise e
        
        except A2ARouterError as e:
            A2A_ROUTER_ERRORS_TOTAL.inc()
            
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error("Error A2ARouterError message", exc_info=e)
            
            return create_a2a_error_response(e, "A2ARouterError", request_envelope, a2aRequest)
        
        except A2ARequestError as e:
            A2A_REQUEST_ERRORS_TOTAL.inc()
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error("Error A2ARequestError message", exc_info=e)
            raise e
        
        except Exception as e:
            A2A_UNCAUGHT_EXCEPTIONS_TOTAL.inc()
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error("Error uncaught Exception", exc_info=e)
            raise e
        
        finally:
            HTTP_REQUEST_DURATION_SECONDS.labels(method="POST",endpoint="/a2a/message").observe(time.time() - start)
            IN_FLIGHT_REQUESTS.dec()

# ---------------------------------
# Entrypoint
# ---------------------------------
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