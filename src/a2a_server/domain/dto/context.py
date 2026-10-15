from dataclasses import dataclass
from typing import Optional, Any
from dataclasses import field

@dataclass(frozen=True)
class SecurityContext:
    """Transport-agnostic security and tracing context for application use cases."""
    
    x_request_id: str
    auth_token: Optional[str] = None

    subject: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    scopes: frozenset[str] = field(default_factory=frozenset)
    claims: dict[str, Any] = field(default_factory=dict)