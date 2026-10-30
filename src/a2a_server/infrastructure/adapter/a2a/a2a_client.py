import logging
import json

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from a2a.client import A2AClientError, A2AClientTimeoutError

from opentelemetry import trace, propagate
from packaging.version import InvalidVersion, Version

from src.a2a_server.config.settings import settings

from typing import Any
from dataclasses import dataclass

from src.a2a_server.domain.dto.context import SecurityContext
from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
)

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    ForbiddenError,
)
from src.a2a_server.common.exceptions.app_error import AppError

#---------------------------------
# Configure logging and tracer
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

@dataclass
class A2aRequest:
    endpoint: str
    skill: str
    payload: dict[str, Any]
    
class A2aAdapter:

    def __init__(self):
        logger.info("Initializing A2aAdapter SUCCESSFULLY")

    async def call(self, request: A2aRequest) -> Any:
        with tracer.start_as_current_span("a2a.client.call") as span:
            span.set_attribute("a2a.endpoint",request.endpoint)
                        
            security = get_security_context()
            headers = {
                    "Authorization": f"Bearer {security.auth_token}",
                    "X-Request-ID": security.x_request_id
            }

            async with httpx.AsyncClient(headers=headers) as httpx_client:
                logger.info("Preparing to call A2A agent at endpoint: %s with skill: %s", request.endpoint, request.skill)
                
                try:
                    resolver = A2ACardResolver(
                        httpx_client=httpx_client,
                        base_url=request.endpoint,
                    )
                    agent_card = await resolver.get_agent_card()
                    
                    client = await create_client(
                        agent=agent_card,
                        client_config=ClientConfig(
                            streaming=False,
                            httpx_client=httpx_client,
                            supported_protocol_bindings=["JSONRPC"],
                        ),
                    )

                    message_payload = {
                        "source_agent": settings.APP_NAME,
                        "target_agent": agent_card.name,
                        "message_type": request.skill,
                        "payload": request.payload,
                    }
                    
                    message = new_text_message(
                        role=Role.ROLE_USER,
                        text=json.dumps(message_payload),
                    )
                    
                    a2a_request = SendMessageRequest(message=message)

                    responses = []
                    async for response in client.send_message(a2a_request):
                        responses.append(response)

                    await client.close()
                    # Return the last response if available, otherwise None
                    return responses[-1] if responses else None
                
                except A2AClientTimeoutError as exc:
                    error_message = str(exc)
                    logger.error(f"A2A client timeout error: {error_message}")
                    span.record_exception(exc)
                    raise AppError(
                        message=f"A2A Client Timeout: {error_message}",
                        error="TIMEOUT",
                        status_code=504
                    ) from exc
                    
                except A2AClientError as exc:
                    error_message = str(exc)
                    logger.error(f"A2A client error: {error_message}")
                    span.record_exception(exc)
                    
                    # Parse HTTP status from error message
                    # Message format: "HTTP Error 401: Client error '401 Unauthorized' for url '...'"
                    if "401" in error_message:
                        raise InvalidAccessTokenError(
                            message=f"A2A Unauthorized: {error_message}",
                            error="UNAUTHORIZED",
                            status_code=401
                        ) from exc
                    
                    elif "403" in error_message:
                        raise ForbiddenError(
                            message=f"A2A Forbidden: {error_message}",
                            error="FORBIDDEN",
                            status_code=403
                        ) from exc
                    
                    elif "400" in error_message:
                        raise AppError(
                            message=f"A2A Bad Request: {error_message}",
                            error="BAD_REQUEST",
                            status_code=400
                        ) from exc
                        
                except Exception as exc:
                    logger.debug(f"Exception type: {type(exc).__name__}")
                    logger.debug(f"Exception: {exc}")
                    logger.debug(f"Exception dir: {[attr for attr in dir(exc) if not attr.startswith('_')]}")
            
                    logger.error("Error calling A2A agent endpoint %s", request.endpoint)
                    span.record_exception(exc)
                    raise