import logging
import os
import httpx2
import json

from opentelemetry import trace

from typing import Dict

from mcp import ClientSession

from mcp.client.streamable_http import streamable_http_client

from src.a2a_server.domain.dto.context import SecurityContext
from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
)

from src.a2a_server.config.settings import settings

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

async def mcp_tool_execution(payload: Dict) -> Dict:
    with tracer.start_as_current_span("mcp.tool_execution") as span:
        logger.info("Executing tool for product with payload: %s", payload)
        mcp_server_inventory_url = settings.MCP_SERVER_INVENTORY_URL
        
        # Establish HTTP connection to the MCP server
        try:
            async with streamable_http_client(mcp_server_inventory_url) as (read_stream, write_stream):
                logger.info("Connected to MCP server at URL: %s", mcp_server_inventory_url)

            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tool_uri = "patch_product"
                logger.info("Executing tool for URI: %s", tool_uri)

                result = await session.call_tool(tool_uri, payload)
                return result.contents[0].text
        except Exception as e:
            logger.error("Exception occurred while executing tool for product with payload: %s, error: %s", payload, e)
            raise e
       
async def mcp_resource_fetcher(resource_uri: str, mcp_server_url: str) -> str:
    logger.info("Fetching resource for URI: %s from MCP server at URL: %s", resource_uri, mcp_server_url)
    
    security = get_security_context()
    headers = {
        "Authorization": f"Bearer {security.auth_token}",
        "X-Request-ID": security.x_request_id
    }
    
    logger.info("Fetching resource for URI: %s with x-request-id: %s headers: %s", resource_uri, headers["X-Request-ID"], headers)
    
    # Capture error responses for later inspection (status code >= 400) for CIMD workflow
    captured = {}
    async def capture_error_response(response):
        if response.status_code >= 400:
            await response.aread()
            captured.update(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.text,
            )

    with tracer.start_as_current_span("mcp.mcp_resource_fetcher") as span:    
        try:
            async with httpx2.AsyncClient(headers=headers, event_hooks={"response": [capture_error_response]}) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        
                        result = await session.read_resource(resource_uri)
                        
                        return result.contents[0].text
                    
        except Exception as e:
            logger.error("Exception occurred while fetching resource for URI: %s, error: %s", resource_uri, e)
            
            status_code = captured.get("status_code", 500)
            
            # Handle captured error responses based on status code for CIMD workflow
            if status_code == 401:
                span.set_attribute("http.status_code", status_code)
                www_authenticate = captured["headers"].get("www-authenticate")
                logger.warning("Response status_code: %s, www-authenticate: %s, body: %s", status_code, www_authenticate, captured["body"])
                return json.dumps({
                    "status_code": 401,
                    "www_authenticate": www_authenticate,
                    "error": "Unauthorized"
                })
            else:
                logger.warning("Response status_code: %s", status_code)
                span.set_attribute("http.status_code", status_code)
                raise e