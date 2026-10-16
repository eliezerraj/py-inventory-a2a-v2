import logging

from pathlib import Path
from cedarpy import (
    PolicySet,
    is_authorized,
)

from src.a2a_server.domain.dto.context import SecurityContext

from src.a2a_server.common.exceptions.auth_error import (
    AuthorizationDeniedError,
)

from src.a2a_server.infrastructure.context.request_context import (
    get_security_context,
)

from opentelemetry import trace

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class CedarVerifier:
    
    def __init__(self):
        logger.info("Initializing CedarVerifier")

        try:
            base_path = Path(__file__).parent.parent.parent.parent
            file_path = base_path / "a2a_server/infrastructure/auth/policy/policy.cedar"
                
            policy_text = Path(file_path).read_text(encoding="utf-8")
            self.policy_set = PolicySet.from_str(policy_text)
            
            logger.info("Policy file read successfully: %s", self.policy_set)
            
        except Exception as e:
            logger.error(f"Failed to read policy file {file_path}: {e}")
            raise e

    def validate(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_attrs: dict | None = None,
        context: dict | None = None,
    ) -> None:

        with tracer.start_as_current_span("cedar_verifier.validate") as span:
            
            security = get_security_context()
            
            request = {
                "principal":
                    f'Client::"{security.subject}"',
                "action":
                    f'Action::"{action}"',
                "resource":
                    f'{resource_type}::"{resource_id}"',
                "context": context or {},
            }

            print("==============================")
            print("Request: %s", request)
            print("==============================")

            entities = [
                {
                    "uid": {
                        "__entity": {
                            "type": "Client",
                            "id": security.subject,
                        }
                    },
                    "attrs": {
                        "client_id": security.subject,
                        "scopes": list(security.scopes),
                    },
                    "parents": [],
                },
                {
                    "uid": {
                        "__entity": {
                            "type": resource_type,
                            "id": resource_id,
                        }
                    },
                    "attrs": resource_attrs or {},
                    "parents": [],
                },
            ]
            print("==============================")
            print("Entities: %s", entities)
            print("==============================")
            
            result = is_authorized(
                request=request,
                policies=self.policy_set,
                entities=entities,
            )

            print("==============================")
            print("Authorization result: %s", result.allowed)
            print("==============================")

            if not result.allowed:
                logger.warning("Authorization denied for action=%s, resource_type=%s, resource_id=%s",action,resource_type,resource_id)
                raise AuthorizationDeniedError(status_code=401, error="UNAUTHORIZED", error_type="InvalidAccessTokenError", message=f"Authorization denied: {action} {resource_type=} {resource_id=}")