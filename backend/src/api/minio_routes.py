from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
from pydantic import BaseModel

from src.api.dependencies import ConfigDep, MinioClientDep
from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error
from src.minio.minio_browser import MinioBrowser
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/minio", tags=["minio"])


def _browser(config: ConfigDep, client: MinioClientDep) -> MinioBrowser:
    return MinioBrowser(client, config.minio_bucket)


@router.get("/ls", response_model=ApiResponse)
def list_prefix(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(default="", description="Prefix to list"),
):
    try:
        data = _browser(config, client).list_prefixes(prefix=prefix)
        return success_response(data, "Prefixes listed successfully")
    except Exception as e:
        logger.error("❌ Error listing prefix '%s': %s", prefix, e)
        raise internal_server_error("Failed to list prefix", str(e))


@router.get("/find", response_model=ApiResponse)
def list_recursive(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(default="", description="Prefix to list recursively"),
    min_size: int = Query(default=0, description="Minimum file size in bytes"),
    max_size: int = Query(default=None, description="Maximum file size in bytes"),
    sort_by: str = Query(default="name", description="Sort by: name or size"),
    sort_order: str = Query(default="asc", regex="^(asc|desc)$", description="Sort order: asc or desc"),
    limit: int = Query(default=1000, description="Maximum number of files to return"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=100, ge=1, le=500, description="Items per page"),
):
    try:
        all_files = _browser(config, client).list_recursive(prefix=prefix)
        
        # Filter by size
        if min_size > 0:
            all_files = [f for f in all_files if f["size"] >= min_size]
        if max_size is not None:
            all_files = [f for f in all_files if f["size"] <= max_size]
        
        # Sort files
        reverse = sort_order == "desc"
        if sort_by == "size":
            all_files.sort(key=lambda x: x["size"], reverse=reverse)
        else:  # sort by name (default)
            all_files.sort(key=lambda x: x["key"], reverse=reverse)
        
        # Apply global limit if specified (before pagination)
        if limit and len(all_files) > limit:
            all_files = all_files[:limit]
        
        # Pagination
        total_items = len(all_files)
        total_pages = (total_items + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = all_files[start_idx:end_idx]
            
        return success_response({
            "items": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }, "Files listed successfully")
    except Exception as e:
        logger.error("❌ Error listing files at '%s': %s", prefix, e)
        raise internal_server_error("Failed to list files", str(e))


@router.get("/preview", response_model=ApiResponse)
def preview_parquet(
    config: ConfigDep,
    client: MinioClientDep,
    key: str = Query(..., description="Object key of Parquet file"),
    limit: int = Query(50, ge=1, le=500, description="Number of rows to preview"),
):
    try:
        data = _browser(config, client).preview_parquet(key=key, limit=limit)
        return success_response(data, "Parquet preview retrieved successfully")
    except Exception as e:
        logger.error("❌ Error previewing parquet '%s': %s", key, e)
        raise internal_server_error("Failed to preview parquet file", str(e))


@router.get("/find-data-files", response_model=ApiResponse)
def find_data_files(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(default="", description="Prefix to search in"),
    min_size: int = Query(default=1000, description="Minimum file size (default: 1KB to skip empty files)"),
    file_type: str = Query(default="parquet", description="File type filter: parquet, json, csv, or all"),
) -> Dict[str, Any]:
    """Find non-empty data files with useful metadata for exploration."""
    try:
        browser = _browser(config, client)
        all_files = browser.list_recursive(prefix=prefix)
        
        # Filter by size (skip small/empty files)
        data_files = [f for f in all_files if f["size"] >= min_size]
        
        # Filter by file type
        if file_type.lower() != "all":
            extension = f".{file_type.lower()}"
            data_files = [f for f in data_files if f["key"].lower().endswith(extension)]
        
        # Sort by size descending (largest files first - likely to have data)
        data_files.sort(key=lambda x: x["size"], reverse=True)
        
        # Add size formatting and categorization
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        
        # Categorize files by size
        large_files = []  # > 10KB
        medium_files = []  # 1KB - 10KB
        small_files = []  # min_size to 1KB
        
        for file in data_files:
            file_info = {
                "key": file["key"],
                "size": file["size"],
                "size_formatted": format_size(file["size"]),
                "filename": file["key"].split("/")[-1]
            }
            
            if file["size"] > 10240:  # > 10KB
                large_files.append(file_info)
            elif file["size"] > 1024:  # 1KB - 10KB
                medium_files.append(file_info)
            else:
                small_files.append(file_info)
        
        return success_response({
            "summary": {
                "total_files": len(data_files),
                "large_files": len(large_files),
                "medium_files": len(medium_files),
                "small_files": len(small_files),
                "search_criteria": {
                    "prefix": prefix,
                    "min_size": min_size,
                    "file_type": file_type
                }
            },
            "large_files": large_files[:20],
            "medium_files": medium_files[:10],
            "small_files": small_files[:5] if small_files else []
        }, "Data files found successfully")
    except Exception as e:
        logger.error("❌ Error finding data files at '%s': %s", prefix, e)
        raise internal_server_error("Failed to find data files", str(e))


class DeleteKeysPayload(BaseModel):
    keys: List[str]


@router.delete("/object", response_model=ApiResponse)
def delete_object(
    config: ConfigDep,
    client: MinioClientDep,
    key: str = Query(..., description="Single object key to delete"),
):
    try:
        data = _browser(config, client).delete_object(key)
        return success_response(data, "Object deleted successfully")
    except Exception as e:
        logger.error("❌ Error deleting object '%s': %s", key, e)
        raise internal_server_error("Failed to delete object", str(e))


@router.post("/delete", response_model=ApiResponse)
def delete_objects(
    config: ConfigDep,
    client: MinioClientDep,
    payload: DeleteKeysPayload,
):
    try:
        data = _browser(config, client).delete_objects(payload.keys)
        return success_response(data, "Objects deleted successfully")
    except Exception as e:
        logger.error("❌ Error deleting %d objects: %s", len(payload.keys), e)
        raise internal_server_error("Failed to delete objects", str(e))


@router.delete("/prefix", response_model=ApiResponse)
def delete_prefix(
    config: ConfigDep,
    client: MinioClientDep,
    prefix: str = Query(..., description="Delete all objects under this prefix"),
):
    try:
        data = _browser(config, client).delete_prefix(prefix)
        return success_response(data, "Prefix deleted successfully")
    except Exception as e:
        logger.error("❌ Error deleting prefix '%s': %s", prefix, e)
        raise internal_server_error("Failed to delete prefix", str(e))
