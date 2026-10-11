import logging
import json

from src.a2a_server.a2a.exception import A2ARequestError, A2ARouterError

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
        
        logger.info("A2AServer initialized SUCCESSFULLY")
    
    async def router(self, envelope):
        with tracer.start_as_current_span("a2a.server.router") as span:
            span.set_attribute("envelope.id", getattr(envelope, "message_id", "unknown"))
            
            try:
                # Skill: Inventory Management
                if envelope.message_type == "inventory.product.check":
                    logger.info("Handling inventory.product.check message type.")
                    
                    response = {"message": "check ok" }
                                        
                    return response
                
                # Skill: Inventory Agent Status
                elif envelope.message_type == "inventory.product.change.price":
                    logger.info("Handling inventory.product.change.price message type.")
                    
                    response = {"message": "pricing ok",
                            }
                    
                    return response
                
                # Skill: Inventory Agent Status
                elif envelope.message_type == "inventory.analyze.stock.coverage":
                    logger.info("Handling inventory.analyze.stock.coverage message type.")
                    
                    response = {"message": "analysis ok",
                            }
                    
                    return response
                
                # Skill: Inventory Agent Status Information
                elif envelope.message_type == "inventory.agent.status":
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
                    
                    response = await self.orchestrator.observe(envelope.payload)
                                        
                    return response

                # Workflow: Inventory Observation
                elif envelope.message_type == "inventory.monitor.device":
                    logger.info("Handling inventory.monitor.decide message type.")
                    
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
