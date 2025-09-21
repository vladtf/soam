// Frontend TypeScript types for the modular data source system

export interface DataSourceType {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  config_schema: JsonSchema;
  enabled: boolean;
  created_at?: string;
  // UI-specific fields from connector display info
  icon?: string;
  category?: string;
  supported_formats?: string[];
  real_time?: boolean;
}

export interface DataSource {
  id: number;
  name: string;
  type_name: string;
  type_display_name: string;
  config: Record<string, any>;
  ingestion_id: string;
  enabled: boolean;
  status: 'inactive' | 'connecting' | 'active' | 'error' | 'stopped';
  created_by?: string;
  last_connection?: string;
  last_error?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CreateDataSourceRequest {
  name: string;
  type_name: string;
  config: Record<string, any>;
  enabled?: boolean;
  created_by?: string;
}

export interface UpdateDataSourceRequest {
  name?: string;
  config?: Record<string, any>;
  enabled?: boolean;
}

export interface DataSourceHealth {
  status: string;
  healthy: boolean;
  endpoint?: string;
  broker?: string;
  port?: number;
  topics?: string[];
  method?: string;
  poll_interval?: number;
  last_successful_poll?: string;
  running?: boolean;
  error?: string;
  message?: string;
}

export interface ConnectorStatusOverview {
  active_connectors: number;
  connectors: Record<string, {
    status: string;
    type: string;
    running: boolean;
    error?: string;
  }>;
}

// JSON Schema types for dynamic form generation
export interface JsonSchemaProperty {
  type: string;
  description?: string;
  default?: any;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  format?: string;
  items?: JsonSchemaProperty;
  oneOf?: JsonSchemaProperty[];
  minItems?: number;
  additionalProperties?: boolean | JsonSchemaProperty;
}

export interface JsonSchema {
  type: string;
  properties: Record<string, JsonSchemaProperty>;
  required?: string[];
  additionalProperties?: boolean;
}
