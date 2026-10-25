import json
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization

public_key_path = Path(__file__).parent / "keys" / "public_key.pem"
public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
public_jwk = json.loads(
    jwt.algorithms.get_default_algorithms()["ES256"].to_jwk(public_key)
)

public_jwk.update(
    {
        "alg": "ES256",
        "kid": "go-inventory-a2a-key-v1",
        "use": "sig",
    }
)

JWKS_METADATA = {"keys": [public_jwk]}