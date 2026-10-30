import logging
import numpy as np
import json
import src.a2a_server.infrastructure.adapter.a2a.a2a_client as a2a_client

from src.a2a_server.domain.dto.model import ProductState                
from src.a2a_server.application.action.action import Action
from src.a2a_server.infrastructure.oauth.oauth import OAuthClient
from src.a2a_server.application.observation.observer import Observer
from src.a2a_server.application.state.builder import Builder
from src.a2a_server.application.reasoning.decider import Decider
from src.a2a_server.config.settings import settings
from src.a2a_server.domain.dto.context import SecurityContext
from src.a2a_server.infrastructure.adapter.a2a.a2a_client import A2aRequest
from src.a2a_server.domain.dto.model import Statistics

from opentelemetry import trace

from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
    reset_security_context,
    set_security_context,
)

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    ForbiddenError,
)

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
        self.a2a_adapter = a2a_client.A2aAdapter()
        
        # Load OAuth client
        self.oauth_client = None
        try:
            self.oauth_client = OAuthClient()
        except Exception as e:
            logger.error("Failed to initialize OAuthClient: %s", e)

    async def _handle_unauthorized(self, audience):
        logger.warning("Unauthorized response received. Requesting a token with a client assertion.")

        if self.oauth_client is None:
            raise RuntimeError("OAuth client is not initialized")

        security = get_security_context()
        if security is None:
            raise RuntimeError("Security context is unavailable")

        client_assertion = self.oauth_client.create_client_assertion()
        context_token = set_security_context(
            SecurityContext(x_request_id=security.x_request_id)
        )
        try:
            token_response = await self.http_adapter.post(
                base_url=settings.AUTHORIZATION_URL_ASSERTION,
                path="/v1/auth/token",
                data={
                    "grant_type": "client_credentials",
                    "resource": audience,
                    "client_id": settings.AUTHORIZATION_CLIENT_ID_ASSERTION,
                    "client_assertion_type": (
                        "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                    ),
                    "client_assertion": client_assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        finally:
            reset_security_context(context_token)

        access_token = (
            token_response.get("access_token")
            if isinstance(token_response, dict)
            else None
        )
        if not access_token:
            logger.error("Authorization server did not return an access token")
            return {
                "error": True,
                "status_code": 502,
                "message": "Failed to obtain access token",
            }

        set_security_context(
            SecurityContext(
                x_request_id=security.x_request_id,
                auth_token=access_token,
            )
        )
        logger.info("Obtained access token SUCCESSFULLY; retrying request")
        
    async def observe(self, payload):
        logger.info(f"observe payload.: payload={payload}")
        with tracer.start_as_current_span("orchestrator.observe"):
            
            response = await self.observer.observe(payload["product"])
            status_code = response.get("status_code")
            
            if status_code == 401:
                print("============== (observe) Starting Unauthorized Protection FLOW OIDC/CIMD ==================")
                await self._handle_unauthorized('py-mcp-inventory-v2')
                return await self.observer.observe(payload["product"])
            elif status_code is not None and status_code >= 400:
                logger.warning("Forbidden response received.")
                           
            return response

    async def state(self, payload):
        logger.info(f"state payload.: payload={payload}")    
        with tracer.start_as_current_span("orchestrator.state"):
            
            response_order_time_series = None
            status_code = None
            
            print(" ****************** STEP 1 build_order_series_state ****************** ")            
            product = payload["product"]
            try:
                response_order_time_series = await self.buildstate.build_order_series_state(product)
                status_code = response_order_time_series.get("status_code")
                
                if status_code == 401:
                    print("============== STEP 1.1 (build_order_series_state) Starting Unauthorized Protection FLOW OIDC/CIMD ==================")
                    await self._handle_unauthorized('py-mcp-order-v2')
                    response_order_time_series = await self.buildstate.build_order_series_state(product)
                    status_code = response_order_time_series.get("status_code")
                
                    print("============== STEP 1.2 (build_order_series_state) After Unauthorized Protection FLOW OIDC/CIMD ==================")
                    print(status_code)
                    print("==================")
                
                    if status_code is not None and status_code != 200:
                        return response_order_time_series
                    
                elif status_code is not None and status_code >= 400:
                    logger.warning("Forbidden response received.")
                    return response_order_time_series
                
            except Exception as e:
                logger.error(f"Error building order series state: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }

            print(" ****************** STEP 2 a2a_adapter availables ****************** ")  
            # Extract amounts and counts from the time series data            
            price = response_order_time_series.get("time_series_order_items", {}).get("product", {}).get("price", {}).get("amount", 0)
            lead_time = response_order_time_series.get("time_series_order_items", {}).get("product", {}).get("lead_time", 0)
            available = response_order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("available", 0)
            sold = response_order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("sold", 0)

            time_series_data = response_order_time_series.get("time_series_order_items", {}).get("time_series_data", [])
            if not time_series_data:
                logger.warning("No time series data available for product: %s", product["sku"])
                return {
                    "error": True,
                    "status_code": 404,
                    "message": "No time series data available",
                    "product": product["sku"]
                }
            
            availables = [item["sum_quantity"] for item in time_series_data if item.get("sum_quantity") is not None]
            response_a2a = None
            statistics_available = None
            request_a2a = A2aRequest(
                endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                skill="statistics.compute",
                payload={
                    "data": availables
                }
            )
    
            try:
                response_a2a = await self.a2a_adapter.call(request_a2a)
                if response_a2a and response_a2a.HasField("message"):
                    for part in response_a2a.message.parts:
                        if part.HasField("text"):
                            statistics_available = json.loads(part.text)
                            break
            except InvalidAccessTokenError as e:
                print("============== STEP 2.1 (a2a_adapter) Starting Unauthorized Protection FLOW OIDC/CIMD ==================")
                logger.warning(f"Invalid access token: {e}")

                await self._handle_unauthorized('py-statistics-a2a-v2')
                response_a2a = await self.a2a_adapter.call(request_a2a)
                
                if response_a2a and response_a2a.HasField("message"):
                    for part in response_a2a.message.parts:
                        if part.HasField("text"):
                            statistics_available = json.loads(part.text)
                            break 
            except ForbiddenError as e:
                logger.warning(f"Access forbidden: {e}")
                return {
                    "error": True,
                    "status_code": 403,
                    "message": str(e),
                    "product": product["sku"]
                }
            except Exception as e:
                logger.error(f"Error computing available statistics: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }

            print(" ****************** STEP 3 a2a_adapter amount ****************** ")  
            
            amount = [item["sum_amount"] for item in time_series_data if item.get("sum_amount") is not None]
            statistics_amount = None
            request_a2a = A2aRequest(
                endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                skill="statistics.compute",
                payload={
                    "data": amount
                }
            )
            
            try:
                response_a2a = await self.a2a_adapter.call(request_a2a)
                if response_a2a and response_a2a.HasField("message"):
                    for part in response_a2a.message.parts:
                        if part.HasField("text"):
                            statistics_amount = json.loads(part.text)
                            break
            except InvalidAccessTokenError as e:
                print("============== STEP 2.1 (a2a_adapter) Starting Unauthorized Protection FLOW OIDC/CIMD ==================")
                logger.warning(f"Invalid access token: {e}")

                await self._handle_unauthorized('py-statistics-a2a-v2')
                response_a2a = await self.a2a_adapter.call(request_a2a)
                
                if response_a2a and response_a2a.HasField("message"):
                    for part in response_a2a.message.parts:
                        if part.HasField("text"):
                            statistics_amount = json.loads(part.text)
                            break 
            except ForbiddenError as e:
                logger.warning(f"Access forbidden: {e}")
                return {
                    "error": True,
                    "status_code": 403,
                    "message": str(e),
                    "product": product["sku"]
                }
            except Exception as e:
                logger.error(f"Error computing available statistics: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }

            # data used to calc inventory amount velocity
            last_amount = amount[-1] if amount else 0
            z =  (last_amount - statistics_amount.get("mean")) / statistics_amount.get("std")
                
            # Sigmoid function to normalize the inventory amount velocity
            level_amount = 1.0 / (1.0 + np.exp(-z))
                
            # Convert the statistics dictionaries to Statistics objects
            statistics_amount = Statistics(**statistics_amount)
            statistics_available = Statistics(**statistics_available)
                                   
            response = {
                "product": {
                            "sku": product["sku"],
                            "lead_time": lead_time,
                            "price": {"amount": price,
                            },
                        },
                "amount": {
                    "level": level_amount,
                    "statistics": statistics_amount,
                },
                "inventory": {
                    "level": np.clip(available / (available + sold) , 0.00, 1.00),
                    "available": available,
                    "sold": sold,
                    "coverage_lead_time": (available / lead_time if lead_time else 1),
                    "statistics": statistics_available,
                },
                "metadata": {
                    "amount": {
                        "data": amount,
                    },
                    "inventory": {
                        "data": availables,
                    },
                }
            }
            
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
                response_observed = await self.observe(payload)
                
                # Check if observer returned an error
                if response_observed.get("error"):
                    logger.warning(f"Observer error: {response_observed.get('message')}")
                    return {
                        "error": True,
                        "status_code": response_observed.get("status_code", 500),
                        "message": response_observed.get("message")
                    }
                
                response_state = await self.state(payload)

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

    #async def deprecated_state(self, payload):
    #    logger.info(f"state payload.: payload={payload}")
    #    with tracer.start_as_current_span("orchestrator.state"):
    #        
    #        response = await self.buildstate.buildstate(payload["product"])
    #        status_code = response.get("status_code")
    #        
    #        if status_code == 401:
    #            await self._handle_unauthorized('py-mcp-order-v2')
    #            return await self.buildstate.buildstate(payload["product"])
    #        elif status_code is not None and status_code >= 400:
    #            logger.warning("Forbidden response received.")
    #                       
    #        return response    
                
    #async def deprecated_premonitor(self, payload):
    #    logger.info(f"monitor payload.: payload={payload}")
    #    with tracer.start_as_current_span("orchestrator.monitor"):
    #        try:
    #            response_observed = await self.observer.observe(payload["product"])    
    #            if response_observed.get("error"):
    #                logger.warning(f"Observer error: {response_observed.get('message')}")
    #                return {
    #                    "error": True,
    #                    "status_code": response_observed.get("status_code", 500),
    #                    "message": response_observed.get("message")
    #                }
    #            response_state = await self.buildstate.buildstate(payload["product"])
    #            product_state = ProductState()
    #            product_state.inventory_level = (response_state.get("inventory") or {}).get("level")
    #            product_state.amount_level = (response_state.get("amount") or {}).get("level")  
    #            response_reasoning = await self.decider.reasoning(product_state)             
    #            print("==============> Response reasoning:", response_reasoning.grid_metadata)            
    #            if "current_state" not in response_reasoning.grid_metadata:
    #                logger.error("Missing current_state in response_reasoning.grid_metadata")
    #                return {"error": "Missing current_state in response_reasoning.grid_metadata, maybe the product not found"}      
    #            current_state = np.array(response_reasoning.grid_metadata.get("current_state", [0.0, 0.0]))   
    #            response_action = self.action.take_action(current_state=current_state)
    #            logger.info(f"Obtained response_action: {response_action}")
    #            response = {
    #                "action": response_action,
    #                "metadata": {
    #                    "observed": response_observed,
    #                    "state": response_state,
    #                    "reasoning": response_reasoning
    #                }
    #            }
    #            return response
    #        except Exception as e:
    #            logger.error(f"Error in monitor: {e}")
    #            return {"error": str(e)}