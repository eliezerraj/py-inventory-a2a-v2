from typing import Optional, Any
from contextvars import ContextVar
from dataclasses import field
from dataclasses import dataclass
from pydantic import Field

@dataclass(frozen=True)
class SecurityContext:
    """Transport-agnostic security and tracing context for application use cases."""
    
    x_request_id: str = field(
        metadata={"description": "The unique request identifier"}
    )
    auth_token: Optional[str] = field(
        default=None,
        metadata={"description": "The authentication token for the request"}
    )

    subject: str | None = field(
        default=None,
        metadata={"description": "The unique identifier for the subject"}
    )
    roles: frozenset[str] = field(
        default_factory=frozenset,
        metadata={"description": "The roles assigned to the subject"}
    )
    scopes: frozenset[str] = field(
        default_factory=frozenset,
        metadata={"description": "The scopes assigned to the subject"}
    )
    claims: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The claims associated with the subject"}
    )

SECURITY_CONTEXT_CTX: ContextVar[SecurityContext | None] = ContextVar(
    "security_context",
    default=None,
)

def set_security_context(context: SecurityContext):
    return SECURITY_CONTEXT_CTX.set(context)

def get_security_context() -> SecurityContext | None:
    return SECURITY_CONTEXT_CTX.get()

def reset_security_context(token):
    SECURITY_CONTEXT_CTX.reset(token)
    
@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    subject: str = Field(
        description="The unique identifier for the verified identity"
    )
    roles: frozenset[str] = Field(
        description="The roles assigned to the verified identity"
    )
    scopes: frozenset[str] = Field(
        description="The scopes assigned to the verified identity"
    )
    claims: dict[str, Any] = Field(
        description="The claims associated with the verified identity"
    )