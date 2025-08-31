"""
Database package initialization.
"""
from .database import get_db, create_tables, Base, SessionLocal, ensure_rule_metrics_columns, ensure_rule_ownership_columns, ensure_computation_ownership_columns, ensure_device_ownership_columns
from .models import Feedback, DashboardTile, ClientError, Device, NormalizationRule, Computation

# Import schema inference models so they're registered with Base
try:
    from ..schema_inference.models import SchemaInfo, SchemaInferenceLog
    _SCHEMA_MODELS_AVAILABLE = True
except ImportError:
    # Schema inference models not available
    _SCHEMA_MODELS_AVAILABLE = False
    SchemaInfo = None
    SchemaInferenceLog = None

__all__ = [
	"get_db",
	"create_tables",
	"Base",
	"SessionLocal",
	"Feedback",
	"DashboardTile",
	"ClientError",
	"Device",
	"NormalizationRule",
	"Computation",
	"ensure_rule_metrics_columns",
	"ensure_rule_ownership_columns",
	"ensure_computation_ownership_columns",
	"ensure_device_ownership_columns",
]

# Add schema models to exports if available
if _SCHEMA_MODELS_AVAILABLE:
    __all__.extend(["SchemaInfo", "SchemaInferenceLog"])
