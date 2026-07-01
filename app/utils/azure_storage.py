import logging
from typing import Optional

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

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
