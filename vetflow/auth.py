import base64
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from flask import request, session

from .config import config

logger = logging.getLogger(__name__)

_JWKS_LOCK = threading.Lock()
_JWKS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "keys": {}}


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401, code: str = "unauthorized") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def is_auth_required() -> bool:
    return bool(getattr(config, "CLERK_AUTH_REQUIRED", False) and (config.CLERK_PUBLISHABLE_KEY or "").strip())


def is_service_api_key_valid() -> bool:
    expected = (getattr(config, "VETFLOW_API_KEY", "") or "").strip()
    if not expected:
        return False
    try:
        header = (
            request.headers.get("X-API-Key")
            or request.headers.get("X-Api-Key")
            or request.headers.get("X-Vetflow-Api-Key")
        )
        if isinstance(header, str) and header.strip() == expected:
            return True
        auth = request.headers.get("Authorization") or ""
        if isinstance(auth, str) and auth.lower().startswith("apikey "):
            return auth.split(" ", 1)[1].strip() == expected
    except RuntimeError:
        return False
    return False


def has_user_session() -> bool:
    try:
        return bool(session.get("current_user_email"))
    except RuntimeError:
        return False


def require_authenticated_request() -> None:
    if is_service_api_key_valid():
        return
    if not is_auth_required():
        return
    if not has_user_session():
        raise AuthError("Inicia sesion para continuar.", 401, "unauthorized")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        return b""
    padding_needed = (-len(value)) % 4
    if padding_needed:
        value = value + ("=" * padding_needed)
    return base64.urlsafe_b64decode(value.encode("utf-8"))


def _decode_publishable_key_domain(publishable_key: str) -> Optional[str]:
    """
    Clerk publishable key: pk_test_<base64(frontend-api + '$')> (o pk_live_...).
    """
    value = (publishable_key or "").strip()
    if not value:
        return None
    parts = value.split("_", 2)
    if len(parts) != 3:
        return None
    if parts[0] != "pk":
        return None
    encoded = parts[2]
    try:
        decoded = _b64url_decode(encoded).decode("utf-8", errors="ignore")
    except Exception:
        return None
    decoded = decoded.split("$", 1)[0].strip()
    return decoded or None


def clerk_issuer() -> str:
    explicit = (config.CLERK_ISSUER or "").strip()
    if explicit:
        return explicit.rstrip("/")
    domain = _decode_publishable_key_domain(config.CLERK_PUBLISHABLE_KEY)
    if domain:
        return f"https://{domain}".rstrip("/")
    return ""


def clerk_jwks_url() -> str:
    explicit = (config.CLERK_JWKS_URL or "").strip()
    if explicit:
        return explicit
    issuer = clerk_issuer()
    if issuer:
        return f"{issuer}/.well-known/jwks.json"
    return ""


def _load_jwks() -> Dict[str, Dict[str, Any]]:
    url = clerk_jwks_url()
    if not url:
        raise AuthError("Falta CLERK_JWKS_URL o CLERK_ISSUER/CLERK_PUBLISHABLE_KEY para validar JWT.", 500, "config")

    now = time.time()
    with _JWKS_LOCK:
        expires_at = float(_JWKS_CACHE.get("expires_at") or 0.0)
        cached = _JWKS_CACHE.get("keys") if expires_at and expires_at > now else None
        if isinstance(cached, dict) and cached:
            return cached

        try:
            res = requests.get(url, timeout=5)
        except Exception as ex:
            raise AuthError(f"No se pudo cargar JWKS de Clerk: {ex}", 503, "jwks_unavailable")
        if res.status_code != 200:
            raise AuthError(
                f"JWKS de Clerk respondio {res.status_code}: {res.text[:200]}",
                503,
                "jwks_unavailable",
            )
        data = res.json() if res.content else {}
        keys = data.get("keys") if isinstance(data, dict) else None
        if not isinstance(keys, list) or not keys:
            raise AuthError("JWKS invalido (sin keys).", 503, "jwks_invalid")

        indexed: Dict[str, Dict[str, Any]] = {}
        for key in keys:
            if not isinstance(key, dict):
                continue
            kid = (key.get("kid") or "").strip()
            if not kid:
                continue
            indexed[kid] = key

        if not indexed:
            raise AuthError("JWKS invalido (sin kids).", 503, "jwks_invalid")

        _JWKS_CACHE["keys"] = indexed
        _JWKS_CACHE["expires_at"] = now + 60 * 60
        return indexed


def _public_key_from_jwk(jwk: Dict[str, Any]):
    if not isinstance(jwk, dict):
        raise AuthError("JWK invalido", 401, "jwt_invalid")
    if (jwk.get("kty") or "").upper() != "RSA":
        raise AuthError("JWK no soportado", 401, "jwt_invalid")
    n_raw = jwk.get("n")
    e_raw = jwk.get("e")
    if not n_raw or not e_raw:
        raise AuthError("JWK incompleto", 401, "jwt_invalid")
    n_int = int.from_bytes(_b64url_decode(str(n_raw)), "big")
    e_int = int.from_bytes(_b64url_decode(str(e_raw)), "big")
    public_numbers = rsa.RSAPublicNumbers(e_int, n_int)
    return public_numbers.public_key()


def _parse_jwt(token: str) -> Tuple[Dict[str, Any], Dict[str, Any], bytes, bytes]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        raise AuthError("JWT malformado", 401, "jwt_malformed")
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64) or b"{}")
        payload = json.loads(_b64url_decode(payload_b64) or b"{}")
    except Exception:
        raise AuthError("JWT invalido", 401, "jwt_invalid")
    signature = _b64url_decode(sig_b64)
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise AuthError("JWT invalido", 401, "jwt_invalid")
    return header, payload, signature, signing_input


def verify_clerk_jwt(token: str) -> Dict[str, Any]:
    header, payload, signature, signing_input = _parse_jwt(token)
    alg = (header.get("alg") or "").strip()
    if alg != "RS256":
        raise AuthError("Algoritmo JWT no soportado", 401, "jwt_invalid")

    expected_issuer = clerk_issuer()
    if expected_issuer:
        issuer = (payload.get("iss") or "").strip().rstrip("/")
        if issuer and issuer != expected_issuer.rstrip("/"):
            raise AuthError("Issuer JWT invalido", 401, "jwt_invalid")

    kid = (header.get("kid") or "").strip()
    if not kid:
        raise AuthError("JWT sin kid", 401, "jwt_invalid")

    jwks = _load_jwks()
    jwk = jwks.get(kid)
    if not jwk:
        with _JWKS_LOCK:
            _JWKS_CACHE["expires_at"] = 0.0
            _JWKS_CACHE["keys"] = {}
        jwks = _load_jwks()
        jwk = jwks.get(kid)
    if not jwk:
        raise AuthError("JWT kid desconocido", 401, "jwt_invalid")

    public_key = _public_key_from_jwk(jwk)
    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise AuthError("Firma JWT invalida", 401, "jwt_invalid")
    except Exception as ex:
        raise AuthError(f"No se pudo validar JWT: {ex}", 401, "jwt_invalid")

    now = int(time.time())
    exp = payload.get("exp")
    nbf = payload.get("nbf")
    if isinstance(exp, (int, float)) and now >= int(exp):
        raise AuthError("JWT expirado", 401, "jwt_expired")
    if isinstance(nbf, (int, float)) and now < int(nbf):
        raise AuthError("JWT aun no valido", 401, "jwt_not_yet_valid")

    return payload


def _email_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    for key in ("email", "email_address", "primary_email"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _name_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    for key in ("name", "full_name", "fullName"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def fetch_clerk_user(clerk_user_id: str) -> Dict[str, Any]:
    secret = (config.CLERK_SECRET_KEY or "").strip()
    if not secret:
        raise AuthError("Falta CLERK_SECRET_KEY para consultar perfil Clerk.", 500, "config")

    user_id = (clerk_user_id or "").strip()
    if not user_id:
        raise AuthError("JWT sin sub", 401, "jwt_invalid")

    url = f"https://api.clerk.com/v1/users/{user_id}"
    try:
        res = requests.get(url, timeout=5, headers={"Authorization": f"Bearer {secret}"})
    except Exception as ex:
        raise AuthError(f"No se pudo consultar Clerk API: {ex}", 503, "clerk_unavailable")
    if res.status_code != 200:
        raise AuthError(
            f"Clerk API respondio {res.status_code}: {res.text[:200]}",
            503 if res.status_code >= 500 else 401,
            "clerk_unavailable",
        )
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
        raise AuthError("Respuesta Clerk invalida", 503, "clerk_unavailable")
    return data


def resolve_user_from_token(token: str) -> Dict[str, Any]:
    claims = verify_clerk_jwt(token)
    clerk_id = (claims.get("sub") or "").strip()
    if not clerk_id:
        raise AuthError("JWT sin sub", 401, "jwt_invalid")

    email = _email_from_claims(claims)
    name = _name_from_claims(claims)

    if not email or not name:
        try:
            profile = fetch_clerk_user(clerk_id)
        except AuthError:
            profile = None

        if profile:
            primary_id = profile.get("primary_email_address_id")
            emails = profile.get("email_addresses") if isinstance(profile.get("email_addresses"), list) else []
            picked = None
            for item in emails:
                if not isinstance(item, dict):
                    continue
                if primary_id and item.get("id") == primary_id:
                    picked = item
                    break
            if not picked and emails:
                picked = emails[0] if isinstance(emails[0], dict) else None
            if not email and picked:
                addr = picked.get("email_address")
                if isinstance(addr, str) and addr.strip():
                    email = addr.strip().lower()

            if not name:
                first = (profile.get("first_name") or "").strip()
                last = (profile.get("last_name") or "").strip()
                joined = f"{first} {last}".strip()
                if joined:
                    name = joined
                else:
                    username = (profile.get("username") or "").strip()
                    name = username or None

    if not email:
        raise AuthError(
            "No se pudo resolver el email del usuario desde el JWT. Configura CLERK_SECRET_KEY o un JWT template que incluya 'email'.",
            400,
            "email_unavailable",
        )

    return {"email": email, "name": name, "clerk_id": clerk_id, "claims": claims}
