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
# -------------------------------    
"""
    Builder
    Responsible for:

    receiving inventory observation data
    building the inventory state
    returning the built inventory state
"""
# ---------------------------------

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

            statistics_available = None
            statistics_amount = None
            response = None
        
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
                elif status_code and status_code >= 400:
                    logger.error(f"Error response from order time series service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Service order time series error",
                        "product": product["sku"]
                    }
                
                time_series_data = order_time_series.get("time_series_order_items", {}).get("time_series_data", [])
                
                # Extract amounts and counts from the time series data            
                price = order_time_series.get("time_series_order_items", {}).get("product", {}).get("price", {}).get("amount", 0)
                lead_time = order_time_series.get("time_series_order_items", {}).get("product", {}).get("lead_time", 0)
                available = order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("available", 0)
                sold = order_time_series.get("time_series_order_items", {}).get("product", {}).get("inventory", {}).get("sold", 0)
                
                # Extract amounts and counts from the time series data
                
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
                reponse_count = A2aRequest(
                    endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                    skill="statistics.compute",
                    payload={
                        "data": availables
                    }
                )
                response_state_count = await self.a2a_adapter.call(reponse_count)
                
                if response_state_count and response_state_count.HasField("message"):
                    for part in response_state_count.message.parts:
                        if part.HasField("text"):
                            statistics_available = json.loads(part.text)
                            break
                # ---------------------------------------------------
                # Compute amounts statistics using the A2A server
                # ---------------------------------------------------
                reponse_amount = A2aRequest(
                    endpoint=settings.A2A_SERVER_STATISTIC_A2A_URL,
                    skill="statistics.compute",
                    payload={
                        "data": amount
                    }
                )
                response_state_amount = await self.a2a_adapter.call(reponse_amount)
                
                if response_state_amount and response_state_amount.HasField("message"):
                    for part in response_state_amount.message.parts:
                        if part.HasField("text"):
                            statistics_amount = json.loads(part.text)
                            break

                # data used to calc inventory amount velocity
                last_amount = amount[-1] if amount else 0
                z =  (last_amount - statistics_amount.get("mean")) / statistics_amount.get("std")
                
                # Sigmoid function to normalize the inventory amount velocity
                level_amount = 1.0 / (1.0 + np.exp(-z))
                
                # Convert the statistics dictionaries to Statistics objects
                statistics_amount = Statistics(**statistics_amount)
                statistics_available = Statistics(**statistics_available)
                                
            except Exception as e:
                logger.error(f"Error fetching order service asynchronously: {e}")
                response = {"message": str(e)}
                    
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