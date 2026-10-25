import logging
import numpy as np

from src.a2a_server.domain.dto.model import ProductState
                
from src.a2a_server.application.action.action import Action
from src.a2a_server.infrastructure.oauth.oauth import OAuthClient
from src.a2a_server.application.observation.observer import Observer
from src.a2a_server.application.state.builder import Builder
from src.a2a_server.application.reasoning.decider import Decider
from src.a2a_server.config.settings import settings
from src.a2a_server.domain.dto.context import SecurityContext

from opentelemetry import trace

from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
    set_security_context,
)

# --------------------------------
"""
InventoryOrchestrator

Responsible for:

coordinating the steps
retrieving state
calling the decision engine
executing the selected action
verifying the result
"""
#---------------------------------

#---------------------------------
# Configure logging and tracer
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class Orchestrator:
    
    def __init__(self, http_adapter):
        logger.info("Orchestrator initialized SUCCESSFULLY")
        
        self.observer = Observer()
        self.buildstate = Builder()
        self.decider = Decider()
        self.action = Action()
        self.http_adapter = http_adapter
        
        # Load OAuth client
        try:
            self.oauth_client = OAuthClient()
        except Exception as e:
            logger.error("Failed to initialize OAuthClient: %s", e)

    async def observe(self, payload):
        logger.info(f"observe payload.: payload={payload}")
        with tracer.start_as_current_span("orchestrator.observe"):
            
            response = await self.observer.observe(payload["product"])
            
            if response["status_code"] == 401:
                print(" =============== Unauthorized response received 401 ===============")
                logger.warning("Unauthorized response received. Attempting to create client assertion.")
                client_assertion = self.oauth_client.create_client_assertion()
                
                base_url = "http://localhost:7100"
                path = "/v1/auth/token"
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                
                response_authorized = await self.http_adapter.post(
                    base_url=base_url,
                    path=path,
                    data={
                        "grant_type": "client_credentials",
                        "resource": "http://py-mcp-order-v2:7501/mcp",
                        "client_id": "http://py-inventory-a2a-v2:7601/oauth/client-metadata.json",
                        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        "client_assertion": client_assertion,
                        },
                    headers={**headers}
                )
                
                print("============= new token ===============>")
                print(response_authorized)
                print("============= new token ===============>")
                
                security = get_security_context()
                sec_context = SecurityContext(
                    x_request_id=security.x_request_id,
                    auth_token=response_authorized.get("access_token"),
                )
                set_security_context(sec_context)
                
                response = await self.observer.observe(payload["product"])
                
                logger.info("========2==========> response=%s", response)
            elif response["status_code"] >= 400:
                logger.warning("Forbidden response received.")
                           
            return response

    async def state(self, payload):
        logger.info(f"state payload.: payload={payload}")
        with tracer.start_as_current_span("orchestrator.state"):
            response = await self.buildstate.buildstate(payload["product"])
            return response

    async def reasoning(self, payload):
        logger.info(f"reasoning payload.: payload={payload}")
        with tracer.start_as_current_span("orchestrator.reasoning"):
            response = await self.decider.reasoning(payload["product_state"])
            return response
           
    async def monitor(self, payload):
        logger.info(f"monitor payload.: payload={payload}")
        with tracer.start_as_current_span("orchestrator.monitor"):
            
            try:
                response_observed = await self.observer.observe(payload["product"])
                
                # Check if observer returned an error
                if response_observed.get("error"):
                    logger.warning(f"Observer error: {response_observed.get('message')}")
                    return {
                        "error": True,
                        "status_code": response_observed.get("status_code", 500),
                        "message": response_observed.get("message")
                    }
                
                response_state = await self.buildstate.buildstate(payload["product"])

                product_state = ProductState()
                product_state.inventory_level = (response_state.get("inventory") or {}).get("level")
                product_state.amount_level = (response_state.get("amount") or {}).get("level")
                
                response_reasoning = await self.decider.reasoning(product_state)
                
                print("==============> Response reasoning:", response_reasoning.grid_metadata)
                
                if "current_state" not in response_reasoning.grid_metadata:
                    logger.error("Missing current_state in response_reasoning.grid_metadata")
                    return {"error": "Missing current_state in response_reasoning.grid_metadata, maybe the product not found"}
                
                current_state = np.array(response_reasoning.grid_metadata.get("current_state", [0.0, 0.0]))
                
                response_action = self.action.take_action(current_state=current_state)

                logger.info(f"Obtained response_action: {response_action}")

                response = {
                    "action": response_action,
                    "metadata": {
                        "observed": response_observed,
                        "state": response_state,
                        "reasoning": response_reasoning
                    }
                }

                return response
            
            except Exception as e:
                logger.error(f"Error in monitor: {e}")
                return {"error": str(e)}