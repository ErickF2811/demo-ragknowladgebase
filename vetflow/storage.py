import logging
from datetime import datetime, timedelta, timezone

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from .config import config

logger = logging.getLogger(__name__)


def _parse_blob_conn(conn_str: str):
    parts = {}
    for chunk in conn_str.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k] = v
    return parts.get("AccountName"), parts.get("AccountKey")


def get_blob_container():
    if not config.AZURE_BLOB_CONN_STR:
        raise RuntimeError("Falta AZURE_BLOB_CONN_STR")
    service = BlobServiceClient.from_connection_string(config.AZURE_BLOB_CONN_STR)
    container_client = service.get_container_client(config.AZURE_BLOB_CONTAINER)
    try:
        container_client.create_container()
        logger.info("Contenedor %s creado en blob storage", config.AZURE_BLOB_CONTAINER)
    except Exception:
        # Ya existe, continuar.
        pass
    return container_client


def upload_blob(blob_name: str, stream, mimetype: str) -> str:
    container = get_blob_container()
    container.upload_blob(
        blob_name,
        stream,
        overwrite=False,
        content_settings=ContentSettings(content_type=mimetype),
    )
    blob_client = container.get_blob_client(blob_name)
    logger.info("Archivo subido a Blob: %s", blob_name)
    return blob_client.url


def delete_blob(blob_path: str):
    try:
        container = get_blob_container()
        container.delete_blob(blob_path, delete_snapshots="include")
        logger.info("Blob eliminado path=%s", blob_path)
    except Exception as ex:
        logger.warning("No se pudo eliminar blob %s: %s", blob_path, ex)


def generate_sas_url(blob_path: str) -> str:
    account_name, account_key = _parse_blob_conn(config.AZURE_BLOB_CONN_STR)
    if not (account_name and account_key):
        raise RuntimeError("No se pudo obtener credenciales para SAS")

    sas = generate_blob_sas(
        account_name=account_name,
        container_name=config.AZURE_BLOB_CONTAINER,
        blob_name=blob_path,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    service = BlobServiceClient.from_connection_string(config.AZURE_BLOB_CONN_STR)
    blob_client = service.get_blob_client(
        container=config.AZURE_BLOB_CONTAINER, blob=blob_path
    )
    return f"{blob_client.url}?{sas}"
