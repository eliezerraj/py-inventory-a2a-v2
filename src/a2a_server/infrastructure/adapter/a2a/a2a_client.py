import logging
import json

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from opentelemetry import trace, propagate
from packaging.version import InvalidVersion, Version

from src.a2a_server.config.settings import settings

from typing import Any
from dataclasses import dataclass

from src.a2a_server.domain.dto.context import SecurityContext
from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
)

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
            
            security = get_security_context()
            headers = {
                    "Authorization": f"Bearer {security.auth_token}",
                    "X-Request-ID": security.x_request_id
            }
                    
            span.set_attribute("a2a.endpoint",request.endpoint)
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

                except Exception as exc:
                    logger.exception("Error calling A2A agent %s",request.endpoint)
                    span.record_exception(exc)
                    raise