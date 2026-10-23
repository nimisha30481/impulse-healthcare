"""Amazon Cognito user pool integration.

Two ways in, both ending in a normal DoseWISE server-side session:
- DoseWISE's own sign-up / sign-in forms call the public Cognito user APIs (SignUp, ConfirmSignUp,
  InitiateAuth USER_PASSWORD_AUTH, ForgotPassword, ChangePassword). Cognito stores the password;
  the backend keeps no password hash for these users. The forms keep every field the brief asks for.
- The hosted UI (authorization-code flow) is still supported for /api/auth/cognito/login.

ID tokens are always verified against the pool's JWKS (issuer, audience, expiry). Cognito groups are
NOT used for patient-level authorisation - that is always done by app/services/permissions.py.
Accounts created before Cognito was switched on (and the demo personas) keep local passwords.
"""
import base64
import hashlib
import hmac
import logging
from functools import lru_cache

import httpx
import jwt
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import verify_password
from app.integrations import aws_services

log = logging.getLogger("impulse.cognito")

FRIENDLY = {
    "CodeMismatchException": "That code isn't correct. Check the latest email from DoseWISE.",
    "ExpiredCodeException": "That code has expired. Request a new one.",
    "InvalidPasswordException": "That password doesn't meet the rules.",
    "LimitExceededException": "Too many attempts. Please wait a few minutes and try again.",
    "TooManyRequestsException": "Too many attempts. Please wait a few minutes and try again.",
    "TooManyFailedAttemptsException": "Too many attempts. Please wait a few minutes and try again.",
}


class CognitoError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code

    def http(self) -> HTTPException:
        status = 429 if "TooMany" in self.code or "Limit" in self.code else 400
        return HTTPException(status, FRIENDLY.get(self.code, "Sign-in service error. Please try again."))


def enabled() -> bool:
    s = get_settings()
    return s.auth_provider == "cognito" and bool(s.cognito_user_pool_id and s.cognito_client_id)


def _issuer() -> str:
    s = get_settings()
    return f"https://cognito-idp.{s.cognito_region}.amazonaws.com/{s.cognito_user_pool_id}"


@lru_cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json")


def verify_id_token(token: str) -> dict:
    s = get_settings()
    key = _jwks_client(_issuer()).get_signing_key_from_jwt(token)
    # leeway: a token Cognito issued this second can look "not yet valid" to a PC clock a moment behind
    claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=s.cognito_client_id, issuer=_issuer(),
                        leeway=120)
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


# ---------------- user APIs used by DoseWISE's own forms ----------------
def _secret_hash(username: str) -> str | None:
    s = get_settings()
    if not s.cognito_client_secret:
        return None
    digest = hmac.new(s.cognito_client_secret.encode(), (username + s.cognito_client_id).encode(), hashlib.sha256)
    return base64.b64encode(digest.digest()).decode()


def _call(op: str, username: str, **kw) -> dict:
    s = get_settings()
    if (h := _secret_hash(username)) is not None:
        if op == "initiate_auth":
            kw["AuthParameters"]["SECRET_HASH"] = h
        else:
            kw["SecretHash"] = h
    try:
        return getattr(aws_services.client("cognito-idp", s.cognito_region or None), op)(ClientId=s.cognito_client_id, **kw)
    except ClientError as e:
        err = e.response.get("Error", {})
        raise CognitoError(err.get("Code", "Unknown"), err.get("Message", "")) from e


def sign_up(email: str, password: str, full_name: str, phone: str | None) -> str:
    attrs = [{"Name": "email", "Value": email}, {"Name": "name", "Value": full_name}]
    if phone and (p := aws_services.e164(phone)):
        attrs.append({"Name": "phone_number", "Value": p})
    return _call("sign_up", email, Username=email, Password=password, UserAttributes=attrs)["UserSub"]


def confirm_sign_up(email: str, code: str) -> None:
    _call("confirm_sign_up", email, Username=email, ConfirmationCode=code)


def resend_code(email: str) -> None:
    _call("resend_confirmation_code", email, Username=email)


def authenticate(email: str, password: str) -> dict:
    r = _call("initiate_auth", email, AuthFlow="USER_PASSWORD_AUTH",
              AuthParameters={"USERNAME": email, "PASSWORD": password})
    if "AuthenticationResult" not in r:
        raise CognitoError(r.get("ChallengeName", "UnsupportedChallenge"))
    return r["AuthenticationResult"]


def forgot_password(email: str) -> None:
    _call("forgot_password", email, Username=email)


def confirm_forgot_password(email: str, code: str, password: str) -> None:
    _call("confirm_forgot_password", email, Username=email, ConfirmationCode=code, Password=password)


def change_password(email: str, old: str, new: str) -> None:
    token = authenticate(email, old)["AccessToken"]
    try:
        aws_services.client("cognito-idp", get_settings().cognito_region or None).change_password(
            PreviousPassword=old, ProposedPassword=new, AccessToken=token)
    except ClientError as e:
        err = e.response.get("Error", {})
        raise CognitoError(err.get("Code", "Unknown"), err.get("Message", "")) from e


def is_cognito_user(user) -> bool:
    return bool(user.cognito_sub) and enabled()


def check_password(user, password: str) -> bool:
    """Password check for any account. Raises CognitoError only for an unconfirmed Cognito user,
    so the sign-in page can ask for the email code instead of saying the password is wrong."""
    if not is_cognito_user(user):
        return verify_password(password, user.password_hash)
    try:
        tokens = authenticate(user.email, password)
    except CognitoError as e:
        if e.code == "UserNotConfirmedException":
            raise
        if e.code in ("NotAuthorizedException", "UserNotFoundException", "PasswordResetRequiredException"):
            return False
        log.warning("Cognito sign-in failed: %s", e)
        raise HTTPException(503, "Sign-in is temporarily unavailable. Please try again in a moment.") from e
    except Exception as e:  # network trouble reaching AWS
        log.exception("Cognito sign-in error")
        raise HTTPException(503, "Sign-in is temporarily unavailable. Please try again in a moment.") from e
    try:
        return verify_id_token(tokens["IdToken"]).get("sub") == user.cognito_sub
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - key fetch or token check problem
        log.exception("Cognito ID token check failed")
        raise HTTPException(503, "Sign-in is temporarily unavailable. Please try again in a moment.") from e
