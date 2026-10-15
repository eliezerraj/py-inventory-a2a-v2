import logging
import json

from src.a2a_server.domain.usecase.calculation import compute_statistics, Statistic
from src.a2a_server.infrastructure.auth.cedar_verifier import CedarVerifier

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    AuthorizationDeniedError,
)
from src.a2a_server.common.exceptions.a2a_error import (
    A2ARequestError,
    A2ARouterError,
)

from opentelemetry.trace.status import Status, StatusCode
from opentelemetry import trace

# -------------------------------    
"""
    A2A Server
    Responsible for:

    receiving A2A messages
    authentication/authorization
    routing
    returning the result
"""
# ---------------------------------

#---------------------------------
# Configure logging and tracer
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class A2AServer:
    
    def __init__(self, settings, orchestrator):
        self.settings = settings
        
        self.orchestrator = orchestrator
        self.cedar_verifier = CedarVerifier()
        
        logger.info("A2AServer initialized SUCCESSFULLY")
    
    async def router(self, envelope):
        with tracer.start_as_current_span("a2a.server.router") as span:
            span.set_attribute("envelope.id", getattr(envelope, "message_id", "unknown"))
            
            try:
                # Skill: Inventory Management
                if envelope.message_type == "inventory.agent.status":
                    logger.info("Handling inventory.agent.status message type.")
                    
                    response = {"message": "agent status ok",
                                "data": json.dumps(self.settings.dict() if hasattr(self.settings, "dict") else self.settings.__dict__),
                            }
                    return response

                # Workflow: Inventory Observation
                elif envelope.message_type == "inventory.monitor.state":
                    logger.info("Handling inventory.monitor.state message type.")
                    
                    response = await self.orchestrator.state(envelope.payload)        
                    return response
                                                
                # Workflow: Inventory Observation
                elif envelope.message_type == "inventory.monitor.observe":
                    logger.info("Handling inventory.monitor.observe message type.")
                    
                    if self.settings.AUTHORIZATION_DRY_RUN:
                        logger.info("Authorization dry run enabled, skipping Cedar verification.")
                    else:
                        self.cedar_verifier.validate(
                            action="send_message",
                            resource_type="MessageType",
                            resource_id=envelope.message_type,
                            resource_attrs={"data": envelope.payload},
                        )
                                            
                    response = await self.orchestrator.observe(envelope.payload)
                    return response

                # Workflow: Inventory Observation
                elif envelope.message_type == "inventory.monitor.device":
                    logger.info("Handling inventory.monitor.device message type.")
                    
                    response = await self.orchestrator.reasoning(envelope.payload)     
                    return response
                                                
                # Workflow: Inventory Monitoring
                elif envelope.message_type == "inventory.monitor":
                    logger.info("Handling inventory.monitor message type.")
                    
                    response = await self.orchestrator.monitor(envelope.payload)
                    return response
                
                else:
                    logger.error("Handling unsupported message type.")
                    message = f"Unsupported message type: {envelope.message_type}"
                    raise A2ARouterError(message)

            except A2ARouterError as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error("Error A2ARouterError message", exc_info=e)
                raise e

            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error("Error uncaught Exception", exc_info=e)
                raise e
