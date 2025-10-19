/**
 * TypeScript interfaces for Value Transformation system
 */

export type TransformationType = 'filter' | 'aggregate' | 'convert' | 'validate';

export interface ValueTransformationRule {
  id: number;
  ingestion_id: string | null;
  field_name: string;
  transformation_type: TransformationType;
  transformation_config: string; // JSON string
  order_priority: number;
  enabled: boolean;
  applied_count: number;
  last_applied_at: string | null;
  created_by: string;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValueTransformationRuleCreate {
  ingestion_id?: string | null;
  field_name: string;
  transformation_type: TransformationType;
  transformation_config: string;
  order_priority?: number;
  enabled?: boolean;
  created_by: string;
}

export interface ValueTransformationRuleUpdate {
  ingestion_id?: string | null;
  field_name?: string;
  transformation_type?: TransformationType;
  transformation_config?: string;
  order_priority?: number;
  enabled?: boolean;
  updated_by: string;
}

// Transformation configuration schemas for different types
export interface FilterTransformationConfig {
  condition: string; // SQL WHERE condition
  action: 'keep' | 'remove';
}

export interface AggregateTransformationConfig {
  function: 'sum' | 'avg' | 'count' | 'min' | 'max';
  group_by?: string[];
  window?: string; // Time window for aggregation
}

export interface ConvertTransformationConfig {
  target_type: 'string' | 'number' | 'boolean' | 'timestamp';
  format?: string; // For date/time conversions
  scale?: number; // For numeric conversions
}

export interface ValidateTransformationConfig {
  rules: Array<{
    type: 'range' | 'regex' | 'enum' | 'not_null';
    parameters: Record<string, any>;
    action: 'warn' | 'reject' | 'correct';
  }>;
}

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

export interface ApiListResponse<T> {
  success: boolean;
  data: T[];
  message: string;
  total?: number;
}

// Transformation type definitions for form dropdowns
export interface TransformationTypeDefinition {
  type: TransformationType;
  label: string;
  description: string;
  configSchema: Record<string, any>;
  examples: Array<{
    name: string;
    config: Record<string, any>;
    description: string;
  }>;
}