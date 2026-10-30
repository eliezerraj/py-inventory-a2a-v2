import logging
import asyncio
import jwt

from typing import Any

from datetime import datetime

from jwt import PyJWKClient

from opentelemetry import trace

from src.a2a_server.domain.dto.model import VerifiedIdentity

from src.a2a_server.common.exceptions.auth_error import (
    InvalidAccessTokenError,
    MissingTokenError,
)

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class JwtTokenVerifier:
    
    def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
        logger.info(f"Initializing JwtTokenVerifier with issuer={issuer} and audience={audience} SUCCESSFULLY")
        
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
                
        if not jwks_url:
            raise ValueError("jwks_url must not be empty")
        
        self.jwks_client = PyJWKClient(
            uri=self.jwks_url,
            cache_keys=True,
        )

    async def verify_token(self, token: str) -> VerifiedIdentity:
        logger.info("Starting token verification")
        print("================= Starting token verification ================")
        print(token)
        print("==============================================================")
        
        with tracer.start_as_current_span("jwt.verify_token") as span:
            try:
                if not token:
                    raise MissingTokenError(status_code=401, error="UNAUTHORIZED", error_type="MissingTokenError", message="Missing token")

                claims = await self._verify_signature_and_claims(token)
                subject = claims.get("sub")

                if not isinstance(subject, str) or not subject:
                    raise InvalidAccessTokenError(status_code=401, error="UNAUTHORIZED", error_type="InvalidAccessTokenError", message="Missing subject claim")

                roles = self._extract_roles(claims)
                scopes = self._extract_scopes(claims)
                
                return VerifiedIdentity(
                    subject=subject,
                    roles=frozenset(roles),
                    scopes=frozenset(scopes),
                    claims=claims,
                )
                
            except jwt.InvalidTokenError as e:
                logger.warning(f"JWT verification failed: {str(e)}")
                raise InvalidAccessTokenError(status_code=401, error="UNAUTHORIZED", error_type="InvalidAccessTokenError", message=f"JWT verification failed: {str(e)}")
            except InvalidAccessTokenError as e:
                logger.warning(f"Invalid access token encountered")
                raise e
            except MissingTokenError as e:
                logger.warning(f"Missing token encountered")
                raise e
            except jwt.PyJWKClientError as e:
                logger.error(f"JWT JWK client error: {str(e)}")
                raise InvalidAccessTokenError(status_code=401, error="UNAUTHORIZED", error_type="InvalidAccessTokenError", message=f"JWK client error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error during token verification: {str(e)}")
                raise InvalidAccessTokenError(status_code=401, error="UNAUTHORIZED", error_type="InvalidAccessTokenError", message=f"Token verification failed: {str(e)}")

    async def _verify_signature_and_claims(self, token: str) -> dict[str, Any]:
        try:
            signing_key = await asyncio.to_thread(self.jwks_client.get_signing_key_from_jwt, token, )
            
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"verify_signature": True, 
                         "verify_exp": True,
                         "require": ["exp", "iss", "aud"],
                    }
            )
            return claims
        except jwt.InvalidTokenError as e:
            raise e
        except InvalidAccessTokenError as e:
            raise e
        except jwt.PyJWKClientError as e:
            raise e
        except Exception as e:
            raise e

    @staticmethod
    def _extract_roles(claims: dict[str, Any]) -> set[str]:
        raw_role = claims.get("role", "")
        if isinstance(raw_role, str):
            return set(raw_role.split())

        if isinstance(raw_role, list):
            return {
                scope for scope in raw_role
                if isinstance(scope, str)
            }

        return set()
    
    @staticmethod
    def _extract_scopes(claims: dict[str, Any]) -> set[str]:
        raw_scope = claims.get("scope", "")
        if isinstance(raw_scope, str):
            return set(raw_scope.split())

        if isinstance(raw_scope, list):
            return {
                scope for scope in raw_scope
                if isinstance(scope, str)
            }

        return set()