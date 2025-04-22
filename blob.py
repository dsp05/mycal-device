
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
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
