import pytest

from app.utils.azure_storage import setup_azure_blob_connection, upload_bytes_to_azure_blob
from app.core.config import settings


class DummyBlobClient:
    def __init__(self, url: str):
        self.url = url
        self.uploaded = None
        self.content_type = None
        self.overwrite = None

    def upload_blob(self, data, overwrite=False, content_type=None):
        self.uploaded = data
        self.overwrite = overwrite
        self.content_type = content_type


class DummyContainerClient:
    def __init__(self, url: str):
        self.url = url
        self.blob_client = DummyBlobClient(url)
        self.created = False

    def create_container(self, exist_ok=False):
        self.created = True

    def get_blob_client(self, blob_name: str):
        self.blob_client.blob_name = blob_name
        return self.blob_client


class DummyBlobServiceClient:
    def __init__(self, url: str):
        self.url = url
        self.container_client = DummyContainerClient(url)

    @classmethod
    def from_connection_string(cls, connection_string: str):
        return cls("https://example.blob.core.windows.net")


def test_setup_azure_blob_connection_uses_connection_string(monkeypatch):
    monkeypatch.setattr(settings, "azure_storage_connection_string", "UseDevelopmentStorage=true")
    monkeypatch.setattr("app.utils.azure_storage.BlobServiceClient", DummyBlobServiceClient)

    client = setup_azure_blob_connection()

    assert client.url == "https://example.blob.core.windows.net"


def test_upload_bytes_to_azure_blob_uploads_and_returns_url(monkeypatch):
    monkeypatch.setattr(settings, "azure_storage_connection_string", "UseDevelopmentStorage=true")
    monkeypatch.setattr(settings, "azure_storage_container_name", "campaign-assets")
    monkeypatch.setattr("app.utils.azure_storage.BlobServiceClient", DummyBlobServiceClient)

    url = upload_bytes_to_azure_blob(
        b"hello world",
        "assets/test.txt",
        content_type="text/plain",
    )

    assert url.endswith("/campaign-assets/assets/test.txt")
