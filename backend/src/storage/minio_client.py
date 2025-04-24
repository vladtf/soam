from io import BytesIO
import os
from minio import Minio
from minio.error import S3Error


class MinioClient:
    def __init__(self):
        self.minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False
        )
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "mybucket")

        # Create bucket if it doesn't exist
        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)

    def upload_data(self, object_name, data: bytes):
        length = len(data)
        if length == 0:
            print("No data to upload.")
            return
        
        data_stream = BytesIO(data)
        try:
            self.minio_client.put_object(
                self.bucket_name,
                object_name,
                data_stream,
                length,
                content_type="application/octet-stream"
            )
            data_stream.close()
                
            print(f"Successfully uploaded {object_name} to {self.bucket_name}.")
        except S3Error as e:
            print(f"Error uploading to MinIO: {e}")


minio_client = MinioClient()
