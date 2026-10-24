import time
import uuid
import jwt
import logging

from pathlib import Path

from src.a2a_server.config.settings import settings

from opentelemetry import trace

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class OAuthClient:
    
    def __init__(self):
        try:
            base_path = Path(__file__).parent.parent.parent.parent
            private_key_path = base_path / "a2a_server/infrastructure/oauth/keys/private_key.pem"
            public_key_path = base_path / "a2a_server/infrastructure/oauth/keys/public_key.pem"

            self.private_key = open(private_key_path).read()
            self.public_key = open(public_key_path).read()
            
            logger.info("Initializing OAuthClient SUCCESSFULLY")
        except Exception as e:
            logger.error("Failed to load keys for OAuthClient: %s", e)
            raise

    def create_client_assertion(self):
        claims = {
            "iss": "http://py-inventory-a2a-v2:7601/oauth/client-metadata.json",
            "sub": "http://py-inventory-a2a-v2:7601/oauth/client-metadata.json",
            "aud": "http://go-authorizer-v2:7100/v1/auth/token",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "jti": str(uuid.uuid4())
        }

        client_assertion = jwt.encode(
            claims,
            self.private_key,
            algorithm="ES256",
            headers={
                "kid": "go-inventory-a2a-key-v1"
            }
        )

        return client_assertion

