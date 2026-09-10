
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
import json
import os


def download():
    blob_service_client = BlobServiceClient(
        os.getenv('BLOB_URL'),
        os.getenv('ACCOUNT_KEY'))
     
    container_client = blob_service_client.get_container_client('mycal')

    for file_path in ['black-b.png', 'red-b.png']:
        blob_client = container_client.get_blob_client(file_path)

        with open(file_path, "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())


def upload_status(status: dict) -> None:
    """Publish a small JSON blob (device-status.json) with the device's
    latest battery level/charging state/wake time, so it can be checked
    remotely (e.g. via `az storage blob download`) without needing to SSH
    into the Pi."""
    blob_service_client = BlobServiceClient(
        os.getenv('BLOB_URL'),
        os.getenv('ACCOUNT_KEY'))

    container_client = blob_service_client.get_container_client('mycal')
    blob_client = container_client.get_blob_client('device-status.json')
    blob_client.upload_blob(
        json.dumps(status),
        overwrite=True,
        content_settings=ContentSettings(content_type='application/json'),
    )
