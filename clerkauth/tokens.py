import json
import jwt
import requests
from django.conf import settings

_jwks_cache = None


def _get_clerk_public_keys():
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    clerk_frontend_api = settings.CLERK_FRONTEND_API
    jwks_url = f"https://{clerk_frontend_api}/.well-known/jwks.json"
    jwks = requests.get(jwks_url).json()
    _jwks_cache = jwks
    return jwks


def _fetch_clerk_user(clerk_user_id):
    """Fetch user details from Clerk Backend API using the user ID."""
    secret_key = settings.CLERK_SECRET_KEY
    resp = requests.get(
        f"https://api.clerk.com/v1/users/{clerk_user_id}",
        headers={"Authorization": f"Bearer {secret_key}"},
    )
    resp.raise_for_status()
    data = resp.json()
    primary_email_id = data.get("primary_email_address_id")
    for addr in data.get("email_addresses", []):
        if addr["id"] == primary_email_id:
            return addr["email_address"]
    if data.get("email_addresses"):
        return data["email_addresses"][0]["email_address"]
    return None


def jwt_decode_token(token):
    header = jwt.get_unverified_header(token)
    jwks = _get_clerk_public_keys()

    public_key = None
    for jwk in jwks["keys"]:
        if jwk["kid"] == header["kid"]:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    if public_key is None:
        global _jwks_cache
        _jwks_cache = None
        jwks = _get_clerk_public_keys()
        for jwk in jwks["keys"]:
            if jwk["kid"] == header["kid"]:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    if public_key is None:
        raise Exception("Public key not found.")

    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


def get_email_from_payload(payload):
    """Extract email from token payload, falling back to Clerk API."""
    email = payload.get("email")
    if not email:
        clerk_user_id = payload.get("sub")
        if clerk_user_id:
            email = _fetch_clerk_user(clerk_user_id)
    return email
