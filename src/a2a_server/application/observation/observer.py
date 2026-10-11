import json
import logging

import src.a2a_server.infrastructure.adapter.mcp.mcp_client as mcp_client

from opentelemetry import trace
from src.a2a_server.config.settings import settings

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class Observer:
    
    def __init__(self):
        logger.info("Observer initialized SUCCESSFULLY")
    
    async def observe(self, product):
        logger.info("Observing product: %s", product)
        with tracer.start_as_current_span("observer.observe"):
            try:
                resource_uri = f"product://{product["sku"]}"
                response = await mcp_client.mcp_resource_fetcher(resource_uri, settings.MCP_SERVER_INVENTORY_URL)
                # If the response is a JSON string, parse it into a dictionary
                if isinstance(response, str):
                    response = json.loads(response)
                    
                # Check for error status codes
                status_code = response.get("status_code")
                if status_code == 404:
                    logger.warning("Product not found: %s", product["sku"])
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Product not found",
                        "product": product["sku"]
                    }
                elif status_code and status_code >= 400:
                    logger.error(f"Error response from inventory service: status_code={status_code}")
                    return {
                        "error": True,
                        "status_code": status_code,
                        "message": "Service Inventory error",
                        "product": product["sku"]
                    }
                    
            except Exception as e:
                logger.error(f"Error fetching inventory service asynchronously: {e}")
                return {
                    "error": True,
                    "status_code": 500,
                    "message": str(e),
                    "product": product["sku"]
                }
                            
        return response
