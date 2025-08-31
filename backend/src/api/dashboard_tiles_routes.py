"""Routes for user-defined dashboard tiles built on computations."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from src.api.models import DashboardTileCreate, DashboardTileUpdate, DashboardTileResponse, ApiResponse
from src.api.response_utils import success_response, not_found_error, bad_request_error
from src.database.database import get_db
from src.database.models import DashboardTile, Computation
from src.computations.executor import ComputationExecutor
from src.api.dependencies import get_spark_manager
from src.spark.spark_manager import SparkManager
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors_sync

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"]) 


@router.get("/tiles", response_model=ApiResponse)
@handle_api_errors_sync("list dashboard tiles")
def list_tiles(db: Session = Depends(get_db)):
    rows = db.query(DashboardTile).order_by(DashboardTile.created_at.desc()).all()
    tiles_data = [DashboardTileResponse(**r.to_dict()) for r in rows]
    return success_response(data=tiles_data, message="Dashboard tiles retrieved successfully")


@router.post("/tiles", response_model=ApiResponse)
@handle_api_errors_sync("create dashboard tile")
def create_tile(payload: DashboardTileCreate, db: Session = Depends(get_db)):
    # Validate computation exists
    comp = db.get(Computation, payload.computation_id)
    if not comp:
        raise HTTPException(status_code=400, detail="Computation not found")
    
    row = DashboardTile(
        name=payload.name,
        computation_id=payload.computation_id,
        viz_type=payload.viz_type,
        config=json.dumps(payload.config or {}),
        layout=json.dumps(payload.layout) if payload.layout is not None else None,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    tile_data = DashboardTileResponse(**row.to_dict())
    return success_response(data=tile_data, message="Dashboard tile created successfully")


@router.patch("/tiles/{tile_id}", response_model=ApiResponse)
@handle_api_errors_sync("update dashboard tile")
def update_tile(tile_id: int, payload: DashboardTileUpdate, db: Session = Depends(get_db)):
    row = db.get(DashboardTile, tile_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.name is not None:
        row.name = payload.name
    if payload.computation_id is not None:
        if not db.get(Computation, payload.computation_id):
            raise HTTPException(status_code=400, detail="Computation not found")
        row.computation_id = payload.computation_id
    if payload.viz_type is not None:
        row.viz_type = payload.viz_type
    if payload.config is not None:
        row.config = json.dumps(payload.config or {})
    if payload.layout is not None:
        row.layout = json.dumps(payload.layout) if payload.layout is not None else None
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    tile_data = DashboardTileResponse(**row.to_dict())
    return success_response(data=tile_data, message="Dashboard tile updated successfully")


@router.delete("/tiles/{tile_id}", response_model=ApiResponse)
@handle_api_errors_sync("delete dashboard tile")
def delete_tile(tile_id: int, db: Session = Depends(get_db)):
    row = db.get(DashboardTile, tile_id)
    if not row:
        not_found_error("Dashboard tile not found")
    db.delete(row)
    db.commit()
    return success_response(message="Dashboard tile deleted successfully")


@router.get("/examples", response_model=ApiResponse)
@handle_api_errors_sync("get dashboard tile examples")
def get_tile_examples(db: Session = Depends(get_db)):
    """Provide example tiles wired to available computations for guidance."""
    comps = db.query(Computation).all()
    examples = []
    if comps:
        # Take first computation as example source
        cid = comps[0].id
        examples = [
            {
                "id": "table-basic",
                "title": "Table of results",
                "tile": {
                    "name": "Results Table",
                    "computation_id": cid,
                    "viz_type": "table",
                    "config": {"columns": []},
                    "enabled": True
                }
            },
            {
                "id": "stat-avg",
                "title": "Single stat",
                "tile": {
                    "name": "Average Value",
                    "computation_id": cid,
                    "viz_type": "stat",
                    "config": {"valueField": "avg_temp", "label": "Avg Temp"},
                    "enabled": True
                }
            }
        ]
    data = {
        "examples": examples,
        "vizTypes": ["table", "stat", "timeseries"],
    }
    return success_response(data=data, message="Dashboard tile examples retrieved successfully")


@router.post("/tiles/{tile_id}/preview", response_model=ApiResponse)
@handle_api_errors_sync("preview dashboard tile")
def preview_tile(tile_id: int, db: Session = Depends(get_db), spark: SparkManager = Depends(get_spark_manager)):
    tile = db.get(DashboardTile, tile_id)
    if not tile:
        not_found_error("Dashboard tile not found")
    comp = db.get(Computation, tile.computation_id)
    if not comp:
        bad_request_error("Computation not found")
    
    defn = json.loads(comp.definition) if comp.definition else {}
    
    # Execute computation using the new executor
    executor = ComputationExecutor(spark)
    data = executor.execute_definition(defn, comp.dataset)
    return success_response(data, "Dashboard tile preview executed successfully")
