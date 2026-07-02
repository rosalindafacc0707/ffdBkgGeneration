import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_azure_blob_connection() -> BlobServiceClient:
    """Create a BlobServiceClient using the configured Azure connection string."""
    connection_string = getattr(settings, "azure_storage_connection_string", None)
    if not connection_string:
        raise ValueError("Azure Storage connection string is not configured")

    client = BlobServiceClient.from_connection_string(connection_string)
    return client


def upload_bytes_to_azure_blob(data: bytes, blob_name: str, *, content_type: Optional[str] = None) -> str:
    """Upload bytes to Azure Blob Storage and return the public blob URL."""
    client = setup_azure_blob_connection()
    container_name = getattr(settings, "azure_storage_container_name", None) or "generatedfiles"

    container_client = getattr(client, "get_container_client", None)
    if callable(container_client):
        container_client = container_client(container_name)
    else:
        container_client = getattr(client, "container_client", None)

    if container_client is None:
        raise AttributeError("Azure Blob client does not expose a container client")

    if hasattr(container_client, "create_container"):
        try:
            container_client.create_container()
        except ResourceExistsError:
            logger.info("Azure container already exists: %s", container_name)

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True, content_type=content_type)

    account_url = getattr(client, "url", "")
    if account_url.endswith("/"):
        account_url = account_url[:-1]

    return f"{account_url}/{container_name}/{blob_name}"


def _extract_blob_name(url: str, container_name: str) -> str:
    """Extract the blob path (relative to the container) from a full blob URL.

    Handles both plain blob URLs and URLs that already carry a (possibly
    expired) query string, e.g. an old/invalid SAS token.
    """
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    prefix = f"{container_name}/"
    if path.startswith(prefix):
        return path[len(prefix):]

    # Fallback: assume the container segment is the first path component
    # and everything after it is the blob name.
    parts = path.split("/", 1)
    if len(parts) == 2:
        return parts[1]
    return path


def generate_product_image_sas_url(product_url: str, *, expiry_minutes: int = 60) -> str:
    """Given a `product_url` pointing to a blob in the (private) products
    container, return a temporary SAS-signed URL that can be used directly
    in an `<img src>` or opened in a browser.

    The products container is a *different* container from the one used
    for generated assets (`AZURE_STORAGE_CONTAINER_NAME`): it is configured
    via `AZURE_STORAGE_CONTAINER_NAME_PRODUCTS` and does not allow public
    (anonymous) access, so the raw URL returned by the briefing extraction
    is not directly reachable — it must be signed first.
    """
    if not product_url:
        raise ValueError("product_url is empty")

    client = setup_azure_blob_connection()
    container_name = getattr(settings, "azure_storage_container_name_products", None)
    if not container_name:
        raise ValueError("AZURE_STORAGE_CONTAINER_NAME_PRODUCTS is not configured")

    account_name = client.account_name
    account_key = getattr(client.credential, "account_key", None)
    if not account_key:
        raise ValueError(
            "Impossibile generare un URL SAS: la connection string configurata "
            "non espone una account key (serve una Shared Key, non una SAS/token credential)."
        )

    blob_name = _extract_blob_name(product_url, container_name)

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
    )

    account_url = client.url.rstrip("/")
    return f"{account_url}/{container_name}/{blob_name}?{sas_token}"