from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
from pydantic import BaseModel

from src.api.dependencies import ConfigDep, MinioClientDep
from src.minio.minio_browser import MinioBrowser



router = APIRouter(prefix="/api/minio", tags=["minio"])


def _browser(config: ConfigDep, client: MinioClientDep) -> MinioBrowser:
    return MinioBrowser(client, config.minio_bucket)


@router.get("/ls")
def list_prefix(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(default="", description="Prefix to list"),
) -> Dict[str, List[str]]:
    try:
        return _browser(config, client).list_prefixes(prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/find")
def list_recursive(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(default="", description="Prefix to list recursively"),
) -> List[Dict[str, Any]]:
    try:
        return _browser(config, client).list_recursive(prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview")
def preview_parquet(
    config: ConfigDep,
    client: MinioClientDep,
    key: str = Query(..., description="Object key of Parquet file"),
    limit: int = Query(50, ge=1, le=500, description="Number of rows to preview"),
) -> Dict[str, Any]:
    try:
        return _browser(config, client).preview_parquet(key=key, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DeleteKeysPayload(BaseModel):
    keys: List[str]


@router.delete("/object")
def delete_object(
    config: ConfigDep,
    client: MinioClientDep,
    key: str = Query(..., description="Single object key to delete"),
) -> Dict[str, Any]:
    try:
        return _browser(config, client).delete_object(key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
def delete_objects(
    config: ConfigDep,
    client: MinioClientDep,
    payload: DeleteKeysPayload,
) -> Dict[str, Any]:
    try:
        return _browser(config, client).delete_objects(payload.keys)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prefix")
def delete_prefix(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(..., description="Delete all objects under this prefix"),
) -> Dict[str, Any]:
    try:
        return _browser(config, client).delete_prefix(prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
