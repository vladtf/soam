"""Routes for user-defined dashboard tiles built on computations."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import DashboardTileCreate, DashboardTileUpdate, DashboardTileResponse
from src.database.database import get_db
from src.database.models import DashboardTile, Computation
from src.computations.computation_routes import _execute_definition
from src.api.dependencies import get_spark_manager
from src.spark.spark_manager import SparkManager

router = APIRouter(prefix="/dashboard", tags=["dashboard"]) 


@router.get("/tiles", response_model=List[DashboardTileResponse])
def list_tiles(db: Session = Depends(get_db)):
    rows = db.query(DashboardTile).order_by(DashboardTile.created_at.desc()).all()
    return [DashboardTileResponse(**r.to_dict()) for r in rows]


@router.post("/tiles", response_model=DashboardTileResponse)
def create_tile(payload: DashboardTileCreate, db: Session = Depends(get_db)):
    # Validate computation exists
    comp = db.get(Computation, payload.computation_id)
    if not comp:
        raise HTTPException(status_code=400, detail="Computation not found")
    import json as _json
    row = DashboardTile(
        name=payload.name,
        computation_id=payload.computation_id,
        viz_type=payload.viz_type,
        config=_json.dumps(payload.config or {}),
        layout=_json.dumps(payload.layout) if payload.layout is not None else None,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return DashboardTileResponse(**row.to_dict())


@router.patch("/tiles/{tile_id}", response_model=DashboardTileResponse)
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
        import json as _json
        row.config = _json.dumps(payload.config or {})
    if payload.layout is not None:
        import json as _json
        row.layout = _json.dumps(payload.layout) if payload.layout is not None else None
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    return DashboardTileResponse(**row.to_dict())


@router.delete("/tiles/{tile_id}")
def delete_tile(tile_id: int, db: Session = Depends(get_db)):
    row = db.get(DashboardTile, tile_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"status": "success", "message": "Deleted"}


@router.get("/examples")
def get_tile_examples(db: Session = Depends(get_db)) -> Dict[str, Any]:
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
    return {
        "examples": examples,
        "vizTypes": ["table", "stat", "timeseries"],
    }


@router.post("/tiles/{tile_id}/preview")
def preview_tile(tile_id: int, db: Session = Depends(get_db), spark: SparkManager = Depends(get_spark_manager)):
    tile = db.get(DashboardTile, tile_id)
    if not tile:
        raise HTTPException(status_code=404, detail="Not found")
    comp = db.get(Computation, tile.computation_id)
    if not comp:
        raise HTTPException(status_code=400, detail="Computation not found")
    import json
    try:
        defn = json.loads(comp.definition)
    except Exception:
        defn = {}
    # Execute computation
    data = _execute_definition(defn, comp.dataset, spark)
    return {"status": "success", "data": data}
