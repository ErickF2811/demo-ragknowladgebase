import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests

from ..config import config

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class EvolutionApiError(RuntimeError):
    pass


def _base_url() -> str:
    base = (config.EVOLUTION_API_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise EvolutionApiError("Configura EVOLUTION_API_BASE_URL")
    return base


def _base_variants() -> list[str]:
    """
    Algunas instalaciones exponen el API en un prefijo distinto al dominio del Manager.
    Probamos variantes comunes para evitar 404 (ej: /api, /v1, /manager/api).
    """
    base = _base_url().rstrip("/")
    variants = [
        base,
        f"{base}/api",
        f"{base}/v1",
        f"{base}/api/v1",
        f"{base}/api/v2",
        f"{base}/manager/api",
    ]
    # unique preserving order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        v = v.rstrip("/")
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _headers() -> Dict[str, str]:
    key = (config.EVOLUTION_API_KEY or "").strip()
    if not key:
        raise EvolutionApiError("Configura EVOLUTION_API_KEY")
    return {
        "apikey": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _extract_qr_base64(payload: Any) -> Optional[str]:
    if payload is None:
        return None

    if isinstance(payload, str):
        value = payload.strip()
        if len(value) > 50:
            return value
        return None

    if isinstance(payload, dict):
        candidates = (
            "base64",
            "qrcode",
            "qr",
            "qrCode",
            "qr_code",
            "qrcodeBase64",
            "qrcode_base64",
            "qrBase64",
            "qr_base64",
        )
        for name in candidates:
            if name in payload:
                found = _extract_qr_base64(payload.get(name))
                if found:
                    return found
        for _, value in payload.items():
            found = _extract_qr_base64(value)
            if found:
                return found

    if isinstance(payload, list):
        for item in payload:
            found = _extract_qr_base64(item)
            if found:
                return found

    return None


def _extract_instance_id(payload: Any) -> Optional[str]:
    """
    Intenta extraer el id/uuid de la instancia desde respuestas de Evolution.
    En el Manager se ve como UUID y suele ser requerido por el endpoint `/webhook/set/<id>`.
    """
    if payload is None:
        return None

    def as_uuid(value: Any) -> Optional[str]:
        if not value:
            return None
        s = str(value).strip()
        return s if _UUID_RE.match(s) else None

    if isinstance(payload, str):
        return as_uuid(payload)

    if isinstance(payload, dict):
        for key in ("id", "instanceId", "instance_id", "uuid"):
            found = as_uuid(payload.get(key))
            if found:
                return found
        for key in ("instance", "data"):
            nested = payload.get(key)
            found = _extract_instance_id(nested)
            if found:
                return found
        for _, v in payload.items():
            found = _extract_instance_id(v)
            if found:
                return found

    if isinstance(payload, list):
        for item in payload:
            found = _extract_instance_id(item)
            if found:
                return found

    return None


def _strip_data_url(value: str) -> str:
    value = (value or "").strip()
    prefix = "data:image/png;base64,"
    if value.lower().startswith(prefix):
        return value[len(prefix) :]
    return value


def create_instance(instance_name: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    instance_name = (instance_name or "").strip()
    if not instance_name:
        raise EvolutionApiError("instance_name_requerido")

    url = f"{_base_url()}/instance/create"
    integration = (config.EVOLUTION_API_INTEGRATION or "").strip()
    # Compat: algunas versiones esperan "integration" (WHATSAPP-BAILEYS) y otras "channel" (Baileys)
    channel = "Baileys" if integration.upper() in ("WHATSAPP-BAILEYS", "BAILEYS") else integration

    # RabbitMQ (Evolution -> eventos)
    default_rabbitmq_events = [
        "CHATS_SET",
        "CHATS_UPDATE",
        "CHATS_UPSERT",
        "CONNECTION_UPDATE",
        "MESSAGES_SET",
        "MESSAGES_UPDATE",
        "MESSAGES_UPSERT",
        "PRESENCE_UPDATE",
        "REMOVE_INSTANCE",
    ]
    rabbitmq_events = config.EVOLUTION_RABBITMQ_EVENTS or default_rabbitmq_events
    body = {
        "instanceName": instance_name,
        "qrcode": True,
        "integration": integration or "Baileys",
        "channel": channel or "Baileys",
    }
    if config.EVOLUTION_RABBITMQ_ENABLED:
        body["rabbitmq"] = {"enabled": True, "events": rabbitmq_events}

    logger.info(
        "Evolution create_instance start instance=%s integration=%s",
        instance_name,
        config.EVOLUTION_API_INTEGRATION,
    )
    try:
        res = requests.post(url, headers=_headers(), json=body, timeout=15)
    except Exception as ex:
        raise EvolutionApiError(f"No se pudo conectar a Evolution API: {ex}") from ex

    if 200 <= res.status_code < 300:
        logger.info("Evolution create_instance ok instance=%s code=%s", instance_name, res.status_code)
        return True, _safe_json(res)
    if res.status_code == 409:
        logger.info("Evolution create_instance exists instance=%s code=%s", instance_name, res.status_code)
        return False, _safe_json(res)

    detail = _response_detail(res)
    logger.warning("Evolution create_instance fail instance=%s code=%s detail=%s", instance_name, res.status_code, detail)
    raise EvolutionApiError(f"Evolution API create falló ({res.status_code}): {detail}")


def connect_qr(instance_name: str) -> Dict[str, Any]:
    instance_name = (instance_name or "").strip()
    if not instance_name:
        raise EvolutionApiError("instance_name_requerido")

    url = f"{_base_url()}/instance/connect/{instance_name}"
    logger.info("Evolution connect_qr start instance=%s", instance_name)
    try:
        res = requests.get(url, headers=_headers(), timeout=15)
    except Exception as ex:
        raise EvolutionApiError(f"No se pudo conectar a Evolution API: {ex}") from ex

    if not (200 <= res.status_code < 300):
        detail = _response_detail(res)
        logger.warning(
            "Evolution connect_qr fail instance=%s code=%s detail=%s",
            instance_name,
            res.status_code,
            detail,
        )
        raise EvolutionApiError(f"Evolution API connect falló ({res.status_code}): {detail}")

    data = _safe_json(res)
    base64 = _extract_qr_base64(data)
    if not base64:
        logger.warning("Evolution connect_qr no_qr instance=%s keys=%s", instance_name, _payload_keys(data))
        raise EvolutionApiError("No encontré el QR base64 en la respuesta de Evolution API")
    base64 = _strip_data_url(base64)

    logger.info("Evolution connect_qr ok instance=%s code=%s bytes=%s", instance_name, res.status_code, len(base64))
    return {"raw": data, "qr_base64": base64}


def ensure_instance_and_get_qr(instance_name: str) -> Dict[str, Any]:
    # Antes de intentar crear/conectar, verificamos si ya está conectado
    # para evitar reiniciar la sesión accidentalmente.
    try:
        status = get_instance_status(instance_name)
        if status.get("connected"):
            logger.info(
                "Evolution ensure_instance_and_get_qr already_connected instance=%s state=%s",
                instance_name,
                status.get("state"),
            )
            # Ya está conectado. No podemos devolver un QR.
            # Devolvemos un indicador especial para que la ruta lo maneje
            return {
                "instance_name": instance_name,
                "created": False,
                "qr_base64": None,
                "qr_data_url": None,
                "already_connected": True
            }
    except EvolutionApiError as ex:
        # Si no podemos validar el estado (red/timeout/etc), NO intentamos crear/conectar
        # porque eso puede regenerar QR y tumbar una sesi�n existente.
        logger.warning("Evolution ensure_instance_and_get_qr status_check_failed instance=%s error=%s", instance_name, ex)
        raise

    created = False
    created_payload: Optional[Dict[str, Any]] = None
    try:
        created, created_payload = create_instance(instance_name)
    except EvolutionApiError as ex:
        # Si falla el create, igual intentamos connect: algunas instalaciones ya tienen la instancia provisionada
        logger.info("Evolution create_instance falló (continuando) instance=%s error=%s", instance_name, ex)

    # WhatsApp webhook removido (usar RabbitMQ si necesitas eventos).

    qr = connect_qr(instance_name)
    qr["instance_name"] = instance_name
    qr["created"] = created
    qr["qr_data_url"] = f"data:image/png;base64,{qr['qr_base64']}"
    return qr


def get_instance_status(instance_name: str) -> Dict[str, Any]:
    """
    Devuelve un dict con:
      - connected: bool|None (None si no pudimos inferir)
      - state: str|None
      - details: dict (campos útiles si existen)
      - raw: respuesta original

    Nota: Evolution API tiene variantes entre versiones; intentamos endpoints comunes.
    """
    instance_name = (instance_name or "").strip()
    if not instance_name:
        raise EvolutionApiError("instance_name_requerido")

    base = _base_url()
    endpoints = [
        f"{base}/instance/connectionState/{instance_name}",
        f"{base}/instance/status/{instance_name}",
        f"{base}/instance/info/{instance_name}",
    ]

    last_error: Optional[str] = None
    saw_not_found = False
    for url in endpoints:
        logger.debug("Evolution status probe instance=%s url=%s", instance_name, url)
        try:
            res = requests.get(url, headers=_headers(), timeout=12)
        except Exception as ex:
            last_error = str(ex)
            continue

        if not (200 <= res.status_code < 300):
            if res.status_code == 404:
                saw_not_found = True
            last_error = f"{res.status_code}: {_response_detail(res)}"
            continue

        data = _safe_json(res)
        connected, state, details = _infer_connection_state(data)
        logger.info(
            "Evolution status ok instance=%s url=%s connected=%s state=%s",
            instance_name,
            url,
            connected,
            state,
        )
        return {
            "connected": connected,
            "state": state,
            "details": details,
            "raw": data,
            "used_url": url,
        }

    # Si todas las rutas típicas devuelven 404, interpretamos como "instancia no creada" (no conectada aún)
    if saw_not_found and last_error and last_error.startswith("404:"):
        logger.info("Evolution status not_created instance=%s", instance_name)
        return {
            "connected": False,
            "state": "not_created",
            "details": {},
            "raw": {"error": "instance_not_found"},
            "used_url": None,
        }

    logger.warning("Evolution status fail instance=%s error=%s", instance_name, last_error or "sin_respuesta")
    raise EvolutionApiError(f"No se pudo consultar estado de la instancia: {last_error or 'sin_respuesta'}")


def resolve_instance_key(instance_name: str) -> Optional[str]:
    """
    En Evolution (según versión/config), el endpoint `/webhook/set/<id>` puede aceptar:
      - el `instanceName` (slug), o
      - el UUID interno (instanceId)
    Por compatibilidad, por defecto devolvemos el `instanceName` (slug), ya que en tu instalación
    el endpoint funciona con el nombre: `/webhook/set/<instanceName>` (según Postman).
    (Deprecated) Este helper quedó de versiones anteriores con webhook.
    """
    instance_name = (instance_name or "").strip()
    if not instance_name:
        return None
    return instance_name


def _lookup_instance_id_from_list(instance_name: str) -> Optional[str]:
    instance_name = (instance_name or "").strip()
    if not instance_name:
        return None

    headers = _headers()
    candidates = []
    for base in _base_variants():
        candidates.extend(
            [
                f"{base}/instance/fetchInstances",
                f"{base}/instance/list",
                f"{base}/instance/all",
                f"{base}/instances",
            ]
        )

    for url in candidates:
        logger.debug("Evolution instances list probe name=%s url=%s", instance_name, url)
        try:
            res = requests.get(url, headers=headers, timeout=15)
        except Exception:
            continue
        if not (200 <= res.status_code < 300):
            continue
        data = _safe_json(res)
        instance_id = _find_instance_id_in_listing(data, instance_name)
        if instance_id:
            logger.info("Evolution instances list ok name=%s id=%s url=%s", instance_name, instance_id, url)
            return instance_id
    return None


def _find_instance_id_in_listing(payload: Any, instance_name: str) -> Optional[str]:
    instance_name = (instance_name or "").strip()
    if not instance_name:
        return None

    if isinstance(payload, dict):
        # common: { instances: [ ... ] } or { data: [ ... ] }
        for key in ("instances", "data", "result"):
            val = payload.get(key)
            found = _find_instance_id_in_listing(val, instance_name)
            if found:
                return found
        # sometimes the instance item is directly here
        name = payload.get("name") or payload.get("instanceName") or payload.get("instance_name")
        if isinstance(name, str) and name.strip() == instance_name:
            return _extract_instance_id(payload)
        # deep search
        for _, v in payload.items():
            found = _find_instance_id_in_listing(v, instance_name)
            if found:
                return found

    if isinstance(payload, list):
        for item in payload:
            found = _find_instance_id_in_listing(item, instance_name)
            if found:
                return found

    return None


def logout_instance(instance_name: str) -> Dict[str, Any]:
    """
    Cierra sesión/desconecta la instancia en Evolution API.
    Importante: esto SOLO debe llamarse por acción explícita del usuario (botón).

    Evolution API puede variar por versión; probamos endpoints comunes.
    """
    instance_name = (instance_name or "").strip()
    if not instance_name:
        raise EvolutionApiError("instance_name_requerido")

    base = _base_url()
    headers = _headers()

    # (method, url)
    candidates = [
        ("POST", f"{base}/instance/logout/{instance_name}"),
        ("POST", f"{base}/instance/disconnect/{instance_name}"),
        ("POST", f"{base}/instance/close/{instance_name}"),
        ("DELETE", f"{base}/instance/delete/{instance_name}"),
    ]

    last_error: Optional[str] = None
    for method, url in candidates:
        logger.info("Evolution logout probe instance=%s method=%s url=%s", instance_name, method, url)
        try:
            if method == "DELETE":
                res = requests.delete(url, headers=headers, timeout=15)
            else:
                res = requests.post(url, headers=headers, json={}, timeout=15)
        except Exception as ex:
            last_error = str(ex)
            continue

        if 200 <= res.status_code < 300:
            data = _safe_json(res)
            logger.info("Evolution logout ok instance=%s code=%s", instance_name, res.status_code)
            return {"ok": True, "used_url": url, "response": data}

        last_error = f"{res.status_code}: {_response_detail(res)}"
        logger.warning("Evolution logout fail instance=%s code=%s detail=%s", instance_name, res.status_code, _response_detail(res))

    raise EvolutionApiError(f"No se pudo cerrar sesión en Evolution API: {last_error or 'sin_respuesta'}")


def _infer_connection_state(payload: Any) -> Tuple[Optional[bool], Optional[str], Dict[str, Any]]:
    details: Dict[str, Any] = {}

    def pick(obj: Any, *keys: str):
        if isinstance(obj, dict):
            for k in keys:
                if k in obj and obj[k] is not None:
                    return obj[k]
        return None

    def as_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    # Algunas respuestas vienen anidadas: { instance: { ... } }
    root = payload
    if isinstance(payload, dict) and isinstance(payload.get("instance"), dict):
        root = payload["instance"]

    state_raw = pick(
        root,
        "state",
        "status",
        "connectionState",
        "connection_status",
        "connectionStatus",
        "instanceStatus",
    )
    state = as_str(state_raw)

    connected_raw = pick(root, "connected", "isConnected", "online", "logged", "authenticated")
    connected: Optional[bool] = None
    if isinstance(connected_raw, bool):
        connected = connected_raw

    # Si no hay boolean, inferir por estado textual
    if connected is None and state:
        normalized = state.lower()
        if normalized in ("open", "connected", "online", "ready", "authenticated", "logged", "active"):
            connected = True
        elif normalized in ("close", "closed", "disconnected", "offline", "error", "connecting", "qr", "qrcode"):
            connected = False

    # Campo "qr" presente suele indicar NO conectado aún
    if connected is None and isinstance(root, dict):
        if any(k in root for k in ("qr", "qrcode", "qrCode", "qr_code", "base64", "qrcodeBase64")):
            connected = False

    # Extraer algunos detalles si existen
    if isinstance(root, dict):
        for key in (
            "number",
            "phone",
            "profileName",
            "profile_name",
            "pushName",
            "push_name",
            "owner",
            "me",
            "jid",
        ):
            val = root.get(key)
            if val is not None:
                details[key] = val

    # Si vienen nested me/owner, dejarlo como dict
    nested = pick(root, "me", "owner")
    if isinstance(nested, dict):
        details.update({f"{'me' if 'me' in root else 'owner'}.{k}": v for k, v in nested.items()})

    return connected, state, details


def _safe_json(res: requests.Response) -> Any:
    try:
        return res.json()
    except Exception:
        return {"text": (res.text or "").strip()}


def _response_detail(res: requests.Response) -> str:
    data = _safe_json(res)
    if isinstance(data, dict):
        for key in ("message", "msg", "error", "detail"):
            if data.get(key):
                return str(data[key])
    return (res.text or "").strip()[:300]


def _payload_keys(payload: Any) -> str:
    try:
        if isinstance(payload, dict):
            return ",".join(list(payload.keys())[:30])
    except Exception:
        pass
    return ""


def _deprecated_removed_webhook_helper(instance_key: str, webhook_url: str) -> Dict[str, Any]:
    """
    (Deprecated) helper removido.
    Best-effort e idempotente: Evolution puede variar por versi�n, por lo que probamos endpoints comunes.
    """
    raise EvolutionApiError("deprecated")
    instance_key = (instance_key or "").strip()
    webhook_url = (webhook_url or "").strip()
    if not instance_key:
        raise EvolutionApiError("instance_name_requerido")
    if not webhook_url:
        raise EvolutionApiError("whatsapp_webhook_url_requerida")

    headers = _headers()

    default_events = [
    "CHATS_SET",
    "CHATS_UPDATE",
    "CHATS_UPSERT",
    "CONNECTION_UPDATE",
    "MESSAGES_SET",
    "MESSAGES_UPDATE",
    "MESSAGES_UPSERT",
    "PRESENCE_UPDATE",
    "REMOVE_INSTANCE",
    ]


    events = default_events
    webhook_headers: Dict[str, str] = {"Content-Type": "application/json"}
    auth = ""
    if auth:
        # Evolution solo reenvía estos headers al webhook (n8n). Mandamos ambas claves por compatibilidad.
        webhook_headers["Authorization"] = auth
        webhook_headers["autorization"] = auth

    body = {
        "rabbitmq": {
            "enabled": True,
            # "url": webhook_url,
            "headers": webhook_headers,
            # "byEvents": False,
            # "base64": False,
            "events": events,
        }
    }

    candidates: list[tuple[str, str]] = []
    for base in _base_variants():
        candidates.extend(
            [
                # endpoint conocido (manager v2.x)
                ("POST", f"{base}/webhook/set/{instance_key}"),
                ("PUT", f"{base}/webhook/set/{instance_key}"),
                # fallback
                ("POST", f"{base}/webhook/{instance_key}"),
                ("PUT", f"{base}/webhook/{instance_key}"),
            ]
        )

    last_error: Optional[str] = None
    for method, url in candidates:
        logger.info(
            "Evolution deprecated probe instance_key=%s method=%s url=%s payload_keys=%s",
            instance_key,
            method,
            url,
            _payload_keys(body),
        )
        try:
            if method == "PUT":
                res = requests.put(url, headers=headers, json=body, timeout=15)
            else:
                res = requests.post(url, headers=headers, json=body, timeout=15)
        except Exception as ex:
            last_error = str(ex)
            continue

        if 200 <= res.status_code < 300:
            data = _safe_json(res)
            logger.info("Evolution deprecated ok instance_key=%s code=%s", instance_key, res.status_code)
            return {"ok": True, "used_url": url, "payload": body, "response": data}

        last_error = f"{res.status_code}: {_response_detail(res)}"
        logger.warning(
            "Evolution deprecated fail instance_key=%s code=%s detail=%s",
            instance_key,
            res.status_code,
            _response_detail(res),
        )

    raise EvolutionApiError(f"deprecated: {last_error or 'sin_respuesta'}")
