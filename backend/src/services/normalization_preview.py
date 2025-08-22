"""
Data normalization preview service.
Provides functionality to preview how normalization rules will transform data
before applying them during the enrichment process.
"""
import logging
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from src.database.models import NormalizationRule
from src.minio.minio_browser import MinioBrowser
import json

logger = logging.getLogger(__name__)


class DataNormalizationPreview:
    """Service for previewing data normalization results."""
    
    def __init__(self, minio_browser: MinioBrowser):
        self.minio_browser = minio_browser
    
    def get_sample_data(self, ingestion_id: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """
        Get sample raw data for preview purposes.
        
        Args:
            ingestion_id: Optional specific ingestion ID to filter by
            limit: Maximum number of records to return
            
        Returns:
            DataFrame with sample raw data
        """
        try:
            # Get recent raw data files using list_recursive from bronze layer
            # Data is stored in bronze/ingestion_id=<id>/date=YYYY-MM-DD/hour=HH/part-uuid.parquet
            prefix = "bronze/"
            if ingestion_id:
                prefix = f"bronze/ingestion_id={ingestion_id}/"
            
            raw_files = self.minio_browser.list_recursive(prefix=prefix)
            
            if not raw_files:
                logger.warning(f"No raw data files found for preview in {prefix}")
                return pd.DataFrame()
            
            # Filter only parquet files and sort by key name (newer dates will be later)
            parquet_files = [f for f in raw_files if f.get('key', '').endswith('.parquet')]
            if not parquet_files:
                logger.warning(f"No parquet files found for preview in {prefix}")
                return pd.DataFrame()
                
            parquet_files.sort(key=lambda x: x.get('key', ''), reverse=True)
            
            sample_data = []
            records_collected = 0
            
            for file_info in parquet_files[:10]:  # Check up to 10 most recent files
                if records_collected >= limit:
                    break
                
                try:
                    file_path = file_info['key']
                    logger.debug(f"Processing file: {file_path}")
                    
                    # Use preview_parquet to get data
                    preview_data = self.minio_browser.preview_parquet(file_path, limit=limit - records_collected)
                    
                    # Convert preview data to DataFrame
                    if preview_data.get('rows'):
                        df = pd.DataFrame(preview_data['rows'])
                        
                        # Add metadata columns
                        df['_source_file'] = file_path
                        df['_ingestion_id'] = self._extract_ingestion_id_from_bronze_path(file_path)
                        
                        remaining_records = limit - records_collected
                        sample_chunk = df.head(remaining_records)
                        sample_data.append(sample_chunk)
                        records_collected += len(sample_chunk)
                        
                        logger.debug(f"Added {len(sample_chunk)} records from {file_path}")
                    
                except Exception as e:
                    logger.warning(f"Failed to read file {file_info['key']}: {e}")
                    continue
            
            if sample_data:
                result_df = pd.concat(sample_data, ignore_index=True)
                logger.info(f"Retrieved {len(result_df)} sample records for preview from bronze layer")
                return result_df
            else:
                logger.warning("No valid data found in bronze layer files")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            return pd.DataFrame()
    
    def preview_normalization(
        self, 
        db: Session,
        sample_data: pd.DataFrame,
        ingestion_id: Optional[str] = None,
        custom_rules: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Preview how normalization rules will transform the sample data.
        
        Args:
            db: Database session
            sample_data: Sample data to transform
            ingestion_id: Optional ingestion ID to filter rules
            custom_rules: Optional custom rules to test (not yet saved)
            
        Returns:
            Dictionary containing preview results
        """
        try:
            if sample_data.empty:
                return {
                    "status": "error",
                    "message": "No sample data available for preview",
                    "original_data": [],
                    "normalized_data": [],
                    "applied_rules": [],
                    "unmapped_columns": []
                }
            
            # Get existing normalization rules
            query = db.query(NormalizationRule).filter(NormalizationRule.enabled == True)
            if ingestion_id:
                query = query.filter(
                    (NormalizationRule.ingestion_id == ingestion_id) |
                    (NormalizationRule.ingestion_id.is_(None))
                )
            
            existing_rules = query.all()
            
            # Combine existing rules with custom rules
            all_rules = []
            
            # Add existing rules
            for rule in existing_rules:
                all_rules.append({
                    "id": rule.id,
                    "raw_key": rule.raw_key.lower(),
                    "canonical_key": rule.canonical_key,
                    "ingestion_id": rule.ingestion_id,
                    "type": "existing"
                })
            
            # Add custom rules if provided
            if custom_rules:
                for i, rule in enumerate(custom_rules):
                    all_rules.append({
                        "id": f"custom_{i}",
                        "raw_key": rule["raw_key"].lower(),
                        "canonical_key": rule["canonical_key"],
                        "ingestion_id": rule.get("ingestion_id"),
                        "type": "custom"
                    })
            
            # Apply normalization rules
            normalized_data = sample_data.copy()
            applied_rules = []
            column_mappings = {}
            
            # Get original column names (case-insensitive mapping)
            original_columns = {col.lower(): col for col in sample_data.columns}
            
            for rule in all_rules:
                raw_key_lower = rule["raw_key"]
                canonical_key = rule["canonical_key"]
                
                # Find matching columns (case-insensitive)
                matching_columns = [
                    original_col for lower_col, original_col in original_columns.items()
                    if raw_key_lower in lower_col or lower_col == raw_key_lower
                ]
                
                for matching_col in matching_columns:
                    if matching_col in normalized_data.columns:
                        # Apply the rule
                        normalized_data = normalized_data.rename(columns={matching_col: canonical_key})
                        column_mappings[matching_col] = canonical_key
                        
                        applied_rules.append({
                            "rule_id": rule["id"],
                            "type": rule["type"],
                            "raw_key": rule["raw_key"],
                            "canonical_key": canonical_key,
                            "matched_column": matching_col,
                            "ingestion_id": rule["ingestion_id"]
                        })
            
            # Find unmapped columns
            unmapped_columns = [
                col for col in sample_data.columns 
                if col not in column_mappings and not col.startswith('_')
            ]
            
            # Prepare response data
            original_sample = sample_data.head(10).to_dict('records')
            normalized_sample = normalized_data.head(10).to_dict('records')
            
            return {
                "status": "success",
                "summary": {
                    "total_records": len(sample_data),
                    "total_columns": len(sample_data.columns),
                    "rules_applied": len(applied_rules),
                    "columns_mapped": len(column_mappings),
                    "unmapped_columns": len(unmapped_columns)
                },
                "original_data": original_sample,
                "normalized_data": normalized_sample,
                "applied_rules": applied_rules,
                "column_mappings": column_mappings,
                "unmapped_columns": unmapped_columns,
                "available_columns": list(sample_data.columns)
            }
            
        except Exception as e:
            logger.error(f"Error previewing normalization: {e}")
            return {
                "status": "error",
                "message": str(e),
                "original_data": [],
                "normalized_data": [],
                "applied_rules": [],
                "unmapped_columns": []
            }
    
    def compare_normalization_scenarios(
        self,
        db: Session,
        sample_data: pd.DataFrame,
        scenario_a_rules: List[Dict[str, Any]],
        scenario_b_rules: List[Dict[str, Any]],
        ingestion_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare two different normalization scenarios side by side.
        
        Args:
            db: Database session
            sample_data: Sample data to transform
            scenario_a_rules: First set of rules to compare
            scenario_b_rules: Second set of rules to compare
            ingestion_id: Optional ingestion ID context
            
        Returns:
            Dictionary containing comparison results
        """
        try:
            scenario_a = self.preview_normalization(db, sample_data, ingestion_id, scenario_a_rules)
            scenario_b = self.preview_normalization(db, sample_data, ingestion_id, scenario_b_rules)
            
            return {
                "status": "success",
                "scenario_a": scenario_a,
                "scenario_b": scenario_b,
                "comparison": {
                    "rules_difference": {
                        "scenario_a_only": len(scenario_a_rules),
                        "scenario_b_only": len(scenario_b_rules),
                    },
                    "mapping_difference": {
                        "scenario_a_mapped": scenario_a["summary"]["columns_mapped"],
                        "scenario_b_mapped": scenario_b["summary"]["columns_mapped"],
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error comparing normalization scenarios: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def validate_normalization_rules(
        self,
        rules: List[Dict[str, Any]],
        sample_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Validate normalization rules against sample data.
        
        Args:
            rules: List of normalization rules to validate
            sample_data: Sample data to validate against
            
        Returns:
            Dictionary containing validation results
        """
        try:
            validation_results = []
            
            # Get available columns (case-insensitive)
            available_columns = {col.lower(): col for col in sample_data.columns}
            
            for i, rule in enumerate(rules):
                raw_key = rule.get("raw_key", "").lower()
                canonical_key = rule.get("canonical_key", "")
                
                result = {
                    "rule_index": i,
                    "raw_key": rule.get("raw_key", ""),
                    "canonical_key": canonical_key,
                    "valid": True,
                    "warnings": [],
                    "errors": []
                }
                
                # Validate raw_key exists
                matching_columns = [
                    orig_col for lower_col, orig_col in available_columns.items()
                    if raw_key in lower_col or lower_col == raw_key
                ]
                
                if not matching_columns:
                    result["valid"] = False
                    result["errors"].append(f"Raw key '{rule.get('raw_key')}' not found in sample data")
                
                # Validate canonical_key is not empty
                if not canonical_key.strip():
                    result["valid"] = False
                    result["errors"].append("Canonical key cannot be empty")
                
                # Check for duplicate canonical keys
                duplicate_canonical = [
                    r for j, r in enumerate(rules) 
                    if j != i and r.get("canonical_key", "") == canonical_key
                ]
                if duplicate_canonical:
                    result["warnings"].append(f"Canonical key '{canonical_key}' is used by multiple rules")
                
                validation_results.append(result)
            
            # Overall validation summary
            valid_rules = [r for r in validation_results if r["valid"]]
            invalid_rules = [r for r in validation_results if not r["valid"]]
            
            return {
                "status": "success",
                "overall_valid": len(invalid_rules) == 0,
                "total_rules": len(rules),
                "valid_rules": len(valid_rules),
                "invalid_rules": len(invalid_rules),
                "validation_details": validation_results
            }
            
        except Exception as e:
            logger.error(f"Error validating normalization rules: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _extract_ingestion_id_from_path(self, file_path: str) -> Optional[str]:
        """Extract ingestion ID from file path."""
        try:
            # Assuming path structure like: raw/YYYY/MM/DD/HH/ingestion_id/file.parquet
            parts = file_path.split('/')
            if len(parts) >= 6:
                return parts[5]  # ingestion_id should be at index 5
            return None
        except Exception:
            return None

    def _extract_ingestion_id_from_bronze_path(self, file_path: str) -> Optional[str]:
        """Extract ingestion ID from bronze layer file path."""
        try:
            # Bronze path structure: bronze/ingestion_id=<id>/date=YYYY-MM-DD/hour=HH/part-uuid.parquet
            parts = file_path.split('/')
            for part in parts:
                if part.startswith('ingestion_id='):
                    return part.split('=', 1)[1]
            return None
        except Exception:
            return None
