"""
Dashboard tile examples and utilities.

This module provides predefined dashboard tile examples that can be used
as templates for creating new tiles, organized by visualization type.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.database.models import Computation
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Static dashboard tile examples that can be customized based on available computations
DASHBOARD_TILE_EXAMPLES = [
    {
        "id": "table-basic",
        "title": "Table of results",
        "description": "Display computation results in a tabular format",
        "viz_type": "table",
        "preferred_computation_type": "table",
        "config": {"columns": []},
        "template": {
            "name": "Results Table",
            "viz_type": "table",
            "config": {"columns": []},
            "enabled": True
        }
    },
    {
        "id": "stat-avg",
        "title": "Single stat",
        "description": "Display a single metric value with optional label",
        "viz_type": "stat",
        "preferred_computation_type": "stat",
        "config": {"valueField": "avg_temperature", "label": "Avg Temp"},
        "template": {
            "name": "Average Value",
            "viz_type": "stat",
            "config": {"valueField": "avg_temperature", "label": "Avg Temp"},
            "enabled": True
        }
    },
    {
        "id": "timeseries-chart",
        "title": "Time series chart",
        "description": "Display data as a time series line chart",
        "viz_type": "timeseries",
        "preferred_computation_type": "timeseries",
        "config": {
            "timeField": "time_start",
            "valueField": "avg_temperature",
            "chartHeight": 250,
            "refreshInterval": 30000,
            "autoRefresh": True
        },
        "template": {
            "name": "Time Series Chart",
            "viz_type": "timeseries",
            "config": {
                "timeField": "time_start",
                "valueField": "avg_temperature",
                "chartHeight": 250,
                "refreshInterval": 30000,
                "autoRefresh": True
            },
            "enabled": True
        }
    },
    {
        "id": "temperature-over-threshold-table",
        "title": "Live Temperature Over Threshold",
        "description": "Monitor live temperature readings exceeding threshold",
        "viz_type": "table",
        "preferred_computation_type": "table",
        "config": {
            "columns": ["sensorId", "temperature", "event_time"],
            "refreshInterval": 10000,
            "autoRefresh": True
        },
        "template": {
            "name": "Live Temperature Over Threshold Detection",
            "viz_type": "table",
            "config": {
                "columns": ["sensorId", "temperature", "event_time"],
                "refreshInterval": 10000,
                "autoRefresh": True
            },
            "enabled": True
        }
    }
]


def get_tile_examples(db: Session) -> Dict[str, Any]:
    """
    Get dashboard tile examples with appropriate computation assignments.
    
    This function intelligently matches tile examples with available computations
    based on their recommended tile types.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary containing examples and metadata
    """
    logger.debug("🔍 Loading dashboard tile examples...")
    
    # Get all available computations
    comps = db.query(Computation).all()
    examples = []
    
    if comps:
        # Group computations by their recommended tile type
        comps_by_tile_type = {
            "table": [],
            "stat": [],
            "timeseries": []
        }
        
        # Categorize computations by their recommended tile type
        for comp in comps:
            if comp.recommended_tile_type in comps_by_tile_type:
                comps_by_tile_type[comp.recommended_tile_type].append(comp)
            else:
                # Default to table if no recommendation or unknown type
                comps_by_tile_type["table"].append(comp)
        
        # Use first computation as fallback for all types
        fallback_comp = comps[0]
        
        # Get computation for each tile type (or fallback to first available)
        table_comp = comps_by_tile_type["table"][0] if comps_by_tile_type["table"] else fallback_comp
        stat_comp = comps_by_tile_type["stat"][0] if comps_by_tile_type["stat"] else fallback_comp
        timeseries_comp = comps_by_tile_type["timeseries"][0] if comps_by_tile_type["timeseries"] else fallback_comp
        
        # Create computation mapping
        computation_map = {
            "table": table_comp,
            "stat": stat_comp,
            "timeseries": timeseries_comp
        }
        
        # Build examples with appropriate computation assignments
        for example in DASHBOARD_TILE_EXAMPLES:
            preferred_type = example.get("preferred_computation_type", "table")
            selected_comp = computation_map.get(preferred_type, fallback_comp)
            
            # Create example with assigned computation
            tile_example = {
                "id": example["id"],
                "title": example["title"],
                "description": example.get("description", ""),
                "tile": {
                    **example["template"],
                    "computation_id": selected_comp.id
                }
            }
            examples.append(tile_example)
            
        logger.info("✅ Generated %d dashboard tile examples with smart computation matching", len(examples))
    else:
        logger.warning("⚠️ No computations available, returning empty examples")
    
    return {
        "examples": examples,
        "vizTypes": ["table", "stat", "timeseries"],
        "total_computations": len(comps),
        "computations_by_type": {
            tile_type: len(comps_by_tile_type.get(tile_type, []))
            for tile_type in ["table", "stat", "timeseries"]
        } if comps else {}
    }