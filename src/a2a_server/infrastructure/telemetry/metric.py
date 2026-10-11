from prometheus_client import Counter, Histogram, Gauge

# Total requests
HTTP_REQUESTS_TOTAL = Counter(
    "a2a_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

# Request duration
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "a2a_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"]
)

# A2A messages received
A2A_MESSAGES_TOTAL = Counter(
    "a2a_messages_total",
    "Total A2A messages received",
    ["message_type"]
)

# A2A router errors
A2A_ROUTER_ERRORS_TOTAL = Counter(
    "a2a_router_errors_total",
    "Total router errors"
)

# In-flight requests
IN_FLIGHT_REQUESTS = Gauge(
    "a2a_in_flight_requests",
    "Current in-flight requests"
)