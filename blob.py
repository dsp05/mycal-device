
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
import json
import os


def download(battery_bucket: str = "unknown"):
    blob_service_client = BlobServiceClient(
        os.getenv('BLOB_URL'),
        os.getenv('ACCOUNT_KEY'))

    container_client = blob_service_client.get_container_client('mycal')

    # The server pre-renders one image variant per battery bucket (it never
    # runs on the Pi) -- download the pair matching this device's own last
    # battery reading, but always save to the same fixed local filenames so
    # the rest of show.py doesn't need to know about buckets.
    remote_names = {
        'black-b.png': f'black-b-{battery_bucket}.png',
        'red-b.png': f'red-b-{battery_bucket}.png',
    }
    for local_name, remote_name in remote_names.items():
        blob_client = container_client.get_blob_client(remote_name)

        with open(local_name, "wb") as download_file:
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
