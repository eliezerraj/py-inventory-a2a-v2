import logging
import asyncio
import json
import numpy as np

import src.a2a_server.infrastructure.adapter.mcp.mcp_client as mcp_client
import src.a2a_server.infrastructure.adapter.a2a.a2a_client as a2a_client
from src.a2a_server.infrastructure.adapter.a2a.a2a_client import A2aRequest
from src.a2a_server.domain.dto.model import Statistics

from src.a2a_server.config.settings import settings

from opentelemetry import trace

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

class Builder:

    def __init__(self):
        self.a2a_adapter = a2a_client.A2aAdapter()
        logger.info("Builder initialized SUCCESSFULLY")
        
    async def buildstate(self, product: dict):
        logger.info("Building state based on: %s", product["sku"])
        with tracer.start_as_current_span("builder.buildstate"):
            try:
                # Fetch order time series data from the MCP server asynchronously
                resource_uri = f"time_series_order_items://{product['sku']}?limit={settings.LIMIT}&offset=0" 
                response_order_time_series = await mcp_client.mcp_resource_fetcher(resource_uri, settings.MCP_SERVER_ORDER_URL)
                order_time_series = json.loads(response_order_time_series)
                
                # Check for error status codes
                status_code = order_time_series.get("status_code")
                if status_code == 404:
                    logger.error("Failed to fetch order time series data: %s", order_time_series)
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Product not found",
                        "product": product["sku"]
                    }
                elif status_code == 401: # Handle captured error responses based on status code for CIMD workflow
                    logger.warning("STARTING Unauthorized Protection FLOW for product: %s", product["sku"])

                    # Extract www-authenticate header for OIDC/CIMD flow
                    www_authenticate = order_time_series.get("www_authenticate", "")

                    # Parse resource metadata URL from www-authenticate header Format: "Bearer resource_metadata=http://localhost:7501/.well-known/oauth-protected-resource"
                    resource_metadata_url = None                    
                    if www_authenticate and "resource_metadata=" in www_authenticate:
                        try:
                            resource_metadata_url = www_authenticate.split("resource_metadata=")[1].strip()
                            logger.info("Extracted resource metadata URL: %s", resource_metadata_url)
                        except Exception as parse_error:
                            logger.error("Failed to parse resource_metadata URL: %s", parse_error)

                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Unauthorized access - OIDC/CIMD flow required: " + order_time_series['message'] if 'message' in order_time_series and 'error' in order_time_series['message'] else "",
                        "product": product["sku"],
                        "www_authenticate": www_authenticate,
                        "resource_metadata_url": resource_metadata_url,
                    }
                elif status_code and status_code == 403:    
                    logger.error(f"Forbidden response from order time series service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Forbidden access to order time series service : " + order_time_series['message'] if 'message' in order_time_series and 'error' in order_time_series['message'] else "",
                        "product": product["sku"]
                    }
                elif status_code and status_code >= 400:
                    logger.error(f"Error response from order time series service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Service order time series Internal error",
                        "product": product["sku"]
                    }

            except Exception as e:
                logger.error(f"Error fetching order mcp_resource_fetcher asynchronously: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }
        
            print("---------------0 ")
                            
            # Extract amounts and counts from the time series data            
            price = order_time_series.get("time_series_order_items", {}).get("product", {}).get("price", {}).get("amount", 0)
            lead_time = order_time_series.get("time_series_order_items", {}).get("product", {}).get("lead_time", 0)
            available = order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("available", 0)
            sold = order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("sold", 0)
                
            print("---------------1 ")
                
            # Extract amounts and counts from the time series data
            time_series_data = order_time_series.get("time_series_order_items", {}).get("time_series_data", [])
            if not time_series_data:
                logger.warning("No time series data available for product: %s", product["sku"])
                return {
                    "error": True,
                    "status_code": 404,
                    "message": "No time series data available",
                    "product": product["sku"]
                }
                
            amount = [item["sum_amount"] for item in time_series_data if item.get("sum_amount") is not None]
            availables = [item["sum_quantity"] for item in time_series_data if item.get("sum_quantity") is not None]

            # ---------------------------------------------------
            # Compute amounts statistics using the A2A server
            # --------------------------------------------------  
            print("---------------2 ")
            statistics_available = None        
            try:    
                reponse_count = A2aRequest(
                    endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                    skill="statistics.compute",
                    payload={
                        "data": availables
                    }
                )
                response_state_count = await self.a2a_adapter.call(reponse_count)

                print("---------------3 ")
                if response_state_count and response_state_count.HasField("message"):
                    for part in response_state_count.message.parts:
                        if part.HasField("text"):
                            statistics_available = json.loads(part.text)
                            break

            except InvalidAccessTokenError as e:
                logger.warning(f"Invalid access token: {e}")
                return {
                    "error": True,
                    "status_code": 401,
                    "message": str(e),
                    "product": product["sku"]
                }
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
            
            # ---------------------------------------------------
            # Compute amounts statistics using the A2A server
            # ---------------------------------------------------
            statistics_amount = None
            try:
                reponse_amount = A2aRequest(
                    endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                    skill="statistics.compute",
                    payload={
                        "data": amount
                    }
                )
                response_state_amount = await self.a2a_adapter.call(reponse_amount)
                print("---------------4 ")
                
                if response_state_amount and response_state_amount.HasField("message"):
                    for part in response_state_amount.message.parts:
                        if part.HasField("text"):
                            statistics_amount = json.loads(part.text)
                            break
                        
            except InvalidAccessTokenError as e:
                logger.warning(f"Invalid access token: {e}")
                return {
                    "error": True,
                    "status_code": 401,
                    "message": str(e),
                    "product": product["sku"]
                }
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
        
    async def build_order_series_state(self, product: dict):
        logger.info("Building build_order_series_state based on: %s", product["sku"])
        with tracer.start_as_current_span("builder.build_order_series_state") as span:
            try:
                # Fetch order time series data from the MCP server asynchronously
                resource_uri = f"time_series_order_items://{product['sku']}?limit={settings.LIMIT}&offset=0" 
                response_order_time_series = await mcp_client.mcp_resource_fetcher(resource_uri, settings.MCP_SERVER_ORDER_URL)
                order_time_series = json.loads(response_order_time_series)
                
                # Check for error status codes
                status_code = order_time_series.get("status_code")
                if status_code == 404:
                    logger.error("Failed to fetch order time series data: %s", order_time_series)
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Product not found",
                        "product": product["sku"]
                    }
                elif status_code == 401: # Handle captured error responses based on status code for CIMD workflow
                    logger.warning("STARTING Unauthorized Protection FLOW for product: %s", product["sku"])

                    # Extract www-authenticate header for OIDC/CIMD flow
                    www_authenticate = order_time_series.get("www_authenticate", "")

                    # Parse resource metadata URL from www-authenticate header Format: "Bearer resource_metadata=http://localhost:7501/.well-known/oauth-protected-resource"
                    resource_metadata_url = None                    
                    if www_authenticate and "resource_metadata=" in www_authenticate:
                        try:
                            resource_metadata_url = www_authenticate.split("resource_metadata=")[1].strip()
                            logger.info("Extracted resource metadata URL: %s", resource_metadata_url)
                        except Exception as parse_error:
                            logger.error("Failed to parse resource_metadata URL: %s", parse_error)

                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Unauthorized access - OIDC/CIMD flow required: " + order_time_series['message'] if 'message' in order_time_series and 'error' in order_time_series['message'] else "",
                        "product": product["sku"],
                        "www_authenticate": www_authenticate,
                        "resource_metadata_url": resource_metadata_url,
                    }
                elif status_code and status_code == 403:    
                    logger.error(f"Forbidden response from order time series service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Forbidden access to order time series service : " + order_time_series['message'] if 'message' in order_time_series and 'error' in order_time_series['message'] else "",
                        "product": product["sku"]
                    }
                elif status_code and status_code >= 400:
                    logger.error(f"Error response from order time series service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Service order time series Internal error",
                        "product": product["sku"]
                    }

                return order_time_series
            
            except Exception as e:
                logger.error(f"Error fetching order mcp_resource_fetcher asynchronously: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }
        
    async def build_statistics_state(self, feature: dict):
        logger.info("Building build_statistics_state based on: %s", feature)
        with tracer.start_as_current_span("builder.build_statistics_state") as span:
            response_statistics = None 
            try:    
                reponse_count = A2aRequest(
                    endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                    skill="statistics.compute",
                    payload={
                        "data": feature
                    }
                )
                response_state_count = await self.a2a_adapter.call(reponse_count)

                if response_state_count and response_state_count.HasField("message"):
                    for part in response_state_count.message.parts:
                        if part.HasField("text"):
                            response_statistics = json.loads(part.text)
                            break

                return response_statistics
            
            except InvalidAccessTokenError as e:
                logger.warning(f"Invalid access token: {e}")
                return {
                    "error": True,
                    "status_code": 401,
                    "message": str(e),
                    "product": product["sku"]
                }
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