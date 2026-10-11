import logging
import os
from opentelemetry import trace

from typing import Dict

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from src.a2a_server.config.settings import settings

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

async def mcp_tool_execution(payload: Dict) -> Dict:
    with tracer.start_as_current_span("mcp.tool_execution") as span:
        logger.info("Executing tool for product with payload: %s", payload)
        mcp_server_inventory_url = settings.MCP_SERVER_INVENTORY_URL
        
        #headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
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
    with tracer.start_as_current_span("mcp.mcp_resource_fetcher") as span:    
        # Establish HTTP connection to the MCP server
        try:
            async with streamable_http_client(mcp_server_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    logger.info("Fetching resource for URI: %s", resource_uri)

                    result = await session.read_resource(resource_uri)
                    
                    return result.contents[0].text
        except Exception as e:
            logger.error("Exception occurred while fetching resource for URI: %s, error: %s", resource_uri, e)
            raise e