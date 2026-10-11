import httpx
import logging
from typing import Any, Optional, Dict

from opentelemetry import trace, propagate
from src.mcp_server.infrastructure.context.request_context import (
    get_security_context,
)

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class HttpAdapter:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        logger.info(f"Initializing HttpAdapter with base_url: {self.base_url} SUCCESSFULLY")

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        """
        Generic HTTP request method.

        :param method: HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
        :param path: URL path (e.g. "/order" or "/order/123")
        :param params: Query string parameters dictionary
        :param payload: JSON body / payload for the request
        :param headers: Additional request headers
        """
        method = method.upper()
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean_path}"

        # Resolve security context
        security_context = get_security_context()
        if security_context is None:
            logger.warning("Security context is not available")

        auth_token = security_context.auth_token if security_context else None
        request_id = security_context.x_request_id if security_context else None

        # Build headers
        merged_headers = {
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {auth_token}"} if auth_token else {}),
            **({"x-request-id": request_id} if request_id else {}),
            **(headers or {}),
        }

        # Inject OpenTelemetry trace context propagation into outgoing headers
        propagate.inject(merged_headers)

        span_name = f"adapter.request HTTP {method} {url}"
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", url)

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=payload,
                        headers=merged_headers,
                        **kwargs,
                    )

                    span.set_attribute("http.status_code", response.status_code)
                    response.raise_for_status()

                    # Handle empty responses (e.g., 204 No Content)
                    if response.status_code == 204 or not response.content:
                        return None

                    return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}"
                )
                span.record_exception(e)
                return None
            except httpx.HTTPError as e:
                logger.error(f"Network/transport error for {method} {url}: {e}")
                span.record_exception(e)
                return None

    # Optional convenience helpers delegating to request():
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Optional[Any]:
        return await self.request("GET", path=path, params=params, **kwargs)

    async def post(self, path: str, payload: Optional[Any] = None, **kwargs: Any) -> Optional[Any]:
        return await self.request("POST", path=path, payload=payload, **kwargs)

    async def put(self, path: str, payload: Optional[Any] = None, **kwargs: Any) -> Optional[Any]:
        return await self.request("PUT", path=path, payload=payload, **kwargs)

    async def delete(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Optional[Any]:
        return await self.request("DELETE", path=path, params=params, **kwargs)