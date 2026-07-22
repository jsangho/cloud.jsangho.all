from __future__ import annotations

import base64

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from auth.domain.services.token_issuer import KID
from fastapi import APIRouter

jwks_router = APIRouter(tags=["auth-jwks"], include_in_schema=False)


def _b64url_uint(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@jwks_router.get("/.well-known/jwks.json")
async def jwks() -> dict[str, list[dict[str, str]]]:
    pem = get_keymaker().get_secret("JWT_PUBLIC_KEY").replace("\\n", "\n")
    public_key = load_pem_public_key(pem.encode())
    if not isinstance(public_key, RSAPublicKey):
        raise RuntimeError("JWT_PUBLIC_KEY가 RSA 공개키가 아닙니다.")

    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KID,
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }
