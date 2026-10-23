"""Amazon Cognito user pool integration (OAuth2 authorization-code flow).

The backend exchanges the code server-side (client secret never reaches the browser), verifies
the ID token signature against the pool's JWKS, checks issuer/audience/expiry, then opens a normal
IMPULSE server-side session. Cognito groups are NOT used for patient-level authorisation - that is
always done by app/services/permissions.py.
"""
from functools import lru_cache

import httpx
import jwt
from fastapi import HTTPException

from app.core.config import get_settings


def _issuer() -> str:
    s = get_settings()
    return f"https://cognito-idp.{s.cognito_region}.amazonaws.com/{s.cognito_user_pool_id}"


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{_issuer()}/.well-known/jwks.json")


def verify_id_token(token: str) -> dict:
    s = get_settings()
    key = _jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=s.cognito_client_id, issuer=_issuer())
    if claims.get("token_use") != "id":
        raise HTTPException(401, "Unexpected token type")
    return claims


def exchange_code_and_verify(code: str) -> dict:
    s = get_settings()
    r = httpx.post(
        f"https://{s.cognito_domain}/oauth2/token",
        data={"grant_type": "authorization_code", "client_id": s.cognito_client_id, "code": code,
              "redirect_uri": s.cognito_redirect_uri},
        auth=(s.cognito_client_id, s.cognito_client_secret) if s.cognito_client_secret else None,
        timeout=10,
    )
    if r.status_code != 200:
        raise HTTPException(401, "Sign-in could not be completed")
    return verify_id_token(r.json()["id_token"])
