"""Routes for user-defined dashboard tiles built on computations."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from src.api.models import DashboardTileCreate, DashboardTileUpdate, DashboardTileResponse, ApiResponse
from src.api.response_utils import success_response, not_found_error, bad_request_error
from src.database.database import get_db
from src.database.models import DashboardTile, Computation, DataSensitivity
from src.computations.executor import ComputationExecutor
from src.computations.sensitivity import can_access_sensitivity, get_restriction_message
from src.api.dependencies import SparkManagerDep
from src.auth.dependencies import get_user_roles_from_token
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors_sync
from src.dashboard.examples import get_tile_examples

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Thread pool for dashboard tile preview operations
# This prevents blocking the FastAPI event loop during Spark computations
_dashboard_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard-api")


def _apply_access_control(tile_dict: dict, user_roles: List[str]) -> dict:
    """Apply access control to a tile based on user roles and sensitivity."""
    sensitivity_str = tile_dict.get("sensitivity", "public")
    try:
        sensitivity = DataSensitivity(sensitivity_str)
    except ValueError:
        sensitivity = DataSensitivity.PUBLIC
    
    can_access = can_access_sensitivity(user_roles, sensitivity)
    logger.debug("🔐 Access check: tile=%s, sensitivity=%s, user_roles=%s, can_access=%s",
                 tile_dict.get("name"), sensitivity_str, user_roles, can_access)
    
    if can_access:
        tile_dict["access_restricted"] = False
        tile_dict["restriction_message"] = None
    else:
        tile_dict["access_restricted"] = True
        tile_dict["restriction_message"] = get_restriction_message(sensitivity, user_roles)
    
    return tile_dict


@router.get("/tiles", response_model=ApiResponse)
@handle_api_errors_sync("list dashboard tiles")
def list_tiles(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """List all dashboard tiles with access control."""
    user_roles = get_user_roles_from_token(authorization, db)
    
    rows = db.query(DashboardTile).order_by(DashboardTile.created_at.desc()).all()
    tiles_data = []
    
    for row in rows:
        tile_dict = row.to_dict()
        tile_dict = _apply_access_control(tile_dict, user_roles)
        tiles_data.append(DashboardTileResponse(**tile_dict))
    
    return success_response(data=tiles_data, message="Dashboard tiles retrieved successfully")


@router.post("/tiles", response_model=ApiResponse)
@handle_api_errors_sync("create dashboard tile")
def create_tile(payload: DashboardTileCreate, db: Session = Depends(get_db)):
    # Validate computation exists
    comp = db.get(Computation, payload.computation_id)
    if not comp:
        raise HTTPException(status_code=400, detail="Computation not found")
    
    # Use custom sensitivity if provided, otherwise inherit from computation
    if payload.sensitivity:
        try:
            sensitivity = DataSensitivity(payload.sensitivity)
        except ValueError:
            valid_sensitivities = ", ".join([s.value for s in DataSensitivity])
            raise bad_request_error(f"Invalid sensitivity level: {payload.sensitivity}. Must be one of: {valid_sensitivities}")
    else:
        sensitivity = comp.sensitivity
    
    row = DashboardTile(
        name=payload.name,
        computation_id=payload.computation_id,
        viz_type=payload.viz_type,
        config=json.dumps(payload.config or {}),
        layout=json.dumps(payload.layout) if payload.layout is not None else None,
        enabled=payload.enabled,
        sensitivity=sensitivity,
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
        comp = db.get(Computation, payload.computation_id)
        if not comp:
            raise HTTPException(status_code=400, detail="Computation not found")
        row.computation_id = payload.computation_id
        # Only update sensitivity from computation if not explicitly provided
        if payload.sensitivity is None:
            row.sensitivity = comp.sensitivity
    if payload.viz_type is not None:
        row.viz_type = payload.viz_type
    if payload.config is not None:
        row.config = json.dumps(payload.config or {})
    if payload.layout is not None:
        row.layout = json.dumps(payload.layout) if payload.layout is not None else None
    if payload.enabled is not None:
        row.enabled = payload.enabled
    # Handle custom sensitivity override
    if payload.sensitivity is not None:
        try:
            row.sensitivity = DataSensitivity(payload.sensitivity)
        except ValueError:
            raise bad_request_error(f"Invalid sensitivity level: {payload.sensitivity}. Must be one of: public, internal, confidential, restricted")
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
        raise not_found_error("Dashboard tile not found")
    db.delete(row)
    db.commit()
    return success_response(message="Dashboard tile deleted successfully")


@router.get("/examples", response_model=ApiResponse)
@handle_api_errors_sync("get dashboard tile examples")
def get_dashboard_tile_examples(db: Session = Depends(get_db)):
    """Provide example tiles wired to computations with their recommended tile types."""
    data = get_tile_examples(db)
    return success_response(data=data, message="Dashboard tile examples retrieved successfully")


@router.post("/tiles/{tile_id}/preview", response_model=ApiResponse)
async def preview_tile(tile_id: int, db: Session = Depends(get_db), spark: SparkManagerDep = None):
    def _execute_tile_preview():
        """Execute tile preview in thread pool."""
        tile = db.get(DashboardTile, tile_id)
        if not tile:
            raise not_found_error("Dashboard tile not found")
        comp = db.get(Computation, tile.computation_id)
        if not comp:
            # Return a special error structure that frontend can detect
            return {
                "error": "COMPUTATION_DELETED",
                "message": f"The computation (ID: {tile.computation_id}) used by this tile has been deleted. Please edit the tile to select a new computation.",
                "tile_name": tile.name,
                "computation_id": tile.computation_id
            }
        
        defn = json.loads(comp.definition) if comp.definition else {}
        
        # Execute computation using the new executor
        executor = ComputationExecutor(spark)
        return executor.execute_definition(defn, comp.dataset)
    
    try:
        # Run Spark computation in thread pool to prevent blocking FastAPI event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_dashboard_executor, _execute_tile_preview)
        return success_response(data, "Dashboard tile preview executed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Dashboard tile preview failed")
        raise bad_request_error(str(e))


@router.post("/tiles/preview", response_model=ApiResponse)
async def preview_tile_config(tile_config: dict, db: Session = Depends(get_db), spark: SparkManagerDep = None):
    """Preview a dashboard tile using tile configuration (for new tiles)."""
    def _execute_config_preview():
        """Execute tile config preview in thread pool."""
        # Validate required fields
        computation_id = tile_config.get("computation_id")
        if not computation_id:
            raise bad_request_error("computation_id is required")
        
        comp = db.get(Computation, computation_id)
        if not comp:
            # Return a special error structure that frontend can detect
            return {
                "error": "COMPUTATION_DELETED",
                "message": f"The computation (ID: {computation_id}) has been deleted. Please select a different computation.",
                "computation_id": computation_id
            }
        
        defn = json.loads(comp.definition) if comp.definition else {}
        
        # Execute computation using the new executor
        executor = ComputationExecutor(spark)
        return executor.execute_definition(defn, comp.dataset)
    
    try:
        # Run Spark computation in thread pool to prevent blocking FastAPI event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_dashboard_executor, _execute_config_preview)
        return success_response(data, "Dashboard tile configuration preview executed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Dashboard tile config preview failed")
        raise bad_request_error(str(e))
