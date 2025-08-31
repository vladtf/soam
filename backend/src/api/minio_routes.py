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
    min_size: int = Query(default=0, description="Minimum file size in bytes"),
    max_size: int = Query(default=None, description="Maximum file size in bytes"),
    sort_by: str = Query(default="name", description="Sort by: name or size"),
    sort_order: str = Query(default="asc", regex="^(asc|desc)$", description="Sort order: asc or desc"),
    limit: int = Query(default=1000, description="Maximum number of files to return"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=100, ge=1, le=500, description="Items per page"),
) -> Dict[str, Any]:
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
            
        return {
            "items": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
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


@router.get("/find-data-files")
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
        
        return {
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
            "large_files": large_files[:20],  # Show top 20 large files
            "medium_files": medium_files[:10],  # Show top 10 medium files
            "small_files": small_files[:5] if small_files else []  # Show few small files
        }
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
