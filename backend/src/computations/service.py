"""Service layer for computation operations."""
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.database.models import Computation, DataSensitivity
from src.api.models import ComputationCreate, ComputationUpdate, ComputationResponse
from src.api.response_utils import not_found_error, conflict_error, bad_request_error
from src.computations.validation import validate_dataset, validate_username, validate_computation_definition
from src.computations.executor import ComputationExecutor
from src.computations.sensitivity import calculate_computation_sensitivity
from src.spark.spark_manager import SparkManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ComputationService:
    """Service for managing computation operations."""
    
    def __init__(self, db: Session, spark_manager: SparkManager = None):
        self.db = db
        self.spark_manager = spark_manager
        self.executor = ComputationExecutor(spark_manager) if spark_manager else None
    
    def list_computations(self) -> List[ComputationResponse]:
        """Get all computations ordered by creation date."""
        rows = self.db.query(Computation).order_by(Computation.created_at.desc()).all()
        return [ComputationResponse(**row.to_dict()) for row in rows]
    
    def create_computation(self, payload: ComputationCreate) -> ComputationResponse:
        """Create a new computation."""
        # Validation
        if not payload.created_by or not payload.created_by.strip():
            raise ValueError("User information required (created_by)")
        
        validated_dataset = validate_dataset(payload.dataset)
        validated_username = validate_username(payload.created_by)
        
        # Validate computation definition
        validation_result = validate_computation_definition(payload.definition)
        if not validation_result.get("valid", False):
            raise bad_request_error(validation_result.get("message", "Invalid computation definition"))
        
        # Check for unique name
        if self.db.query(Computation).filter(Computation.name == payload.name).first():
            raise conflict_error("Computation name already exists")
        
        # Calculate inherited sensitivity from source devices
        sensitivity, source_devices = calculate_computation_sensitivity(self.db, payload.definition)
        
        # Create computation
        computation = Computation(
            name=payload.name,
            description=payload.description,
            dataset=validated_dataset,
            definition=json.dumps(payload.definition),
            recommended_tile_type=payload.recommended_tile_type,
            enabled=payload.enabled,
            created_by=validated_username,
            sensitivity=sensitivity,
            source_devices=source_devices,
        )
        
        self.db.add(computation)
        self.db.commit()
        self.db.refresh(computation)
        
        logger.info("Computation created by '%s': %s (%s)", 
                   validated_username, computation.name, computation.dataset)
        
        return ComputationResponse(**computation.to_dict())
    
    def update_computation(self, comp_id: int, payload: ComputationUpdate) -> ComputationResponse:
        """Update an existing computation."""
        # Validation
        if not payload.updated_by or not payload.updated_by.strip():
            raise ValueError("User information required (updated_by)")
        
        computation = self.db.get(Computation, comp_id)
        if not computation:
            raise not_found_error("Computation not found")
        
        validated_username = validate_username(payload.updated_by)
        
        changes = []
        
        # Update fields if provided and changed
        if payload.description is not None and payload.description != computation.description:
            changes.append(f"description: '{computation.description or ''}' -> '{payload.description}'")
            computation.description = payload.description
        
        if payload.dataset is not None and payload.dataset != computation.dataset:
            new_dataset = validate_dataset(payload.dataset)
            changes.append(f"dataset: '{computation.dataset}' -> '{new_dataset}'")
            computation.dataset = new_dataset
        
        if payload.definition is not None:
            validation_result = validate_computation_definition(payload.definition)
            if not validation_result.get("valid", False):
                raise bad_request_error(validation_result.get("message", "Invalid computation definition"))
            import hashlib
            old_def = json.loads(computation.definition) if computation.definition else {}
            
            def json_hash(obj):
                return hashlib.md5(json.dumps(obj, sort_keys=True).encode('utf-8')).hexdigest()
            
            if json_hash(payload.definition) != json_hash(old_def):
                changes.append("definition updated")
                computation.definition = json.dumps(payload.definition)
                
                # Recalculate sensitivity when definition changes
                new_sensitivity, new_source_devices = calculate_computation_sensitivity(self.db, payload.definition)
                if new_sensitivity != computation.sensitivity:
                    changes.append(f"sensitivity: {computation.sensitivity.value if computation.sensitivity else 'public'} -> {new_sensitivity.value}")
                computation.sensitivity = new_sensitivity
                computation.source_devices = new_source_devices
        
        if payload.recommended_tile_type is not None and payload.recommended_tile_type != computation.recommended_tile_type:
            changes.append(f"recommended_tile_type: '{computation.recommended_tile_type}' -> '{payload.recommended_tile_type}'")
            computation.recommended_tile_type = payload.recommended_tile_type
        
        if payload.enabled is not None and payload.enabled != computation.enabled:
            changes.append(f"enabled: {computation.enabled} -> {payload.enabled}")
            computation.enabled = payload.enabled
        
        computation.updated_by = validated_username
        
        self.db.add(computation)
        self.db.commit()
        self.db.refresh(computation)
        
        if changes:
            logger.info("Computation %d updated by '%s': %s", 
                       computation.id, validated_username, "; ".join(changes))
        else:
            logger.info("Computation %d touched by '%s' (no changes)", 
                       computation.id, validated_username)
        
        return ComputationResponse(**computation.to_dict())
    
    def delete_computation(self, comp_id: int) -> None:
        """Delete a computation."""
        computation = self.db.get(Computation, comp_id)
        if not computation:
            raise not_found_error("Computation not found")
        
        self.db.delete(computation)
        self.db.commit()
        
        logger.info("Computation deleted: %s (id: %d)", computation.name, comp_id)
    
    def check_computation_dependencies(self, comp_id: int) -> Dict[str, Any]:
        """Check if computation has dependent dashboard tiles."""
        from src.database.models import DashboardTile
        
        computation = self.db.get(Computation, comp_id)
        if not computation:
            raise not_found_error("Computation not found")
        
        # Find tiles that use this computation
        dependent_tiles = self.db.query(DashboardTile).filter(
            DashboardTile.computation_id == comp_id
        ).all()
        
        return {
            "computation": {
                "id": computation.id,
                "name": computation.name
            },
            "dependent_tiles": [
                {
                    "id": tile.id,
                    "name": tile.name,
                    "viz_type": tile.viz_type,
                    "enabled": tile.enabled
                }
                for tile in dependent_tiles
            ],
            "can_delete": True,  # We'll allow deletion but warn about consequences
            "has_dependencies": len(dependent_tiles) > 0
        }
    
    def preview_computation(self, comp_id: int) -> List[dict]:
        """Preview a computation's results."""
        if not self.executor:
            raise RuntimeError("Spark manager not available for preview")
        
        computation = self.db.get(Computation, comp_id)
        if not computation:
            raise not_found_error("Computation not found")
        
        try:
            definition = json.loads(computation.definition)
        except Exception as e:
            raise ValueError(f"Invalid JSON definition: {e}")
        
        return self.executor.execute_definition(definition, computation.dataset)
    
    def preview_example(self, example_id: str, example_definition: Dict[str, Any]) -> List[dict]:
        """Preview an example computation."""
        if not self.executor:
            raise RuntimeError("Spark manager not available for preview")
        
        return self.executor.execute_definition(
            example_definition["definition"], 
            example_definition["dataset"]
        )
