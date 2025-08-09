"""Utilities for browsing and previewing data in MinIO."""
from typing import List, Dict, Any
from minio import Minio
import io
import pyarrow.parquet as pq


class MinioBrowser:
    def __init__(self, client: Minio, bucket: str):
        self.client = client
        self.bucket = bucket

    def list_prefixes(self, prefix: str = "", delimiter: str = "/") -> Dict[str, List[str]]:
        """List 'folders' (common prefixes) and objects under a prefix."""
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=False)
        prefixes: List[str] = []
        files: List[str] = []
        for obj in objects:
            if obj.is_dir:
                prefixes.append(obj.object_name)
            else:
                files.append(obj.object_name)
        return {"prefixes": prefixes, "files": files}

    def list_recursive(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List all objects recursively under a prefix, returning key and size."""
        results: List[Dict[str, Any]] = []
        for obj in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            if not obj.is_dir:
                results.append({"key": obj.object_name, "size": obj.size})
        return results

    def preview_parquet(self, key: str, limit: int = 50) -> Dict[str, Any]:
        """Fetch a parquet object and return schema + first N rows as JSON-like structure."""
        response = self.client.get_object(self.bucket, key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()

        buf = io.BytesIO(data)
        table = pq.read_table(buf)
        df = table.to_pandas()
        head_df = df.head(limit)
        schema = {name: str(dtype) for name, dtype in zip(df.columns, df.dtypes)}
        return {"schema": schema, "rows": head_df.to_dict(orient="records")}
