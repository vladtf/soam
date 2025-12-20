// src/config.ts
export interface ExternalServices {
  grafanaUrl: string;
  prometheusUrl: string;
  minioUrl: string;
  sparkMasterUrl: string;
  neo4jUrl: string;
  cadvisorUrl: string;
}

export interface AppConfig {
    backendUrl: string;
    ingestorUrl: string;
    externalServices?: ExternalServices;
  }

// Default URLs for local development
export const defaultExternalServices: ExternalServices = {
  grafanaUrl: 'http://localhost:3001',
  prometheusUrl: 'http://localhost:9091',
  minioUrl: 'http://localhost:9090',
  sparkMasterUrl: 'http://localhost:8080',
  neo4jUrl: 'http://localhost:7474',
  cadvisorUrl: 'http://localhost:8089',
};
  
  let config: AppConfig;
  
  export const loadConfig = async (): Promise<AppConfig> => {
    if (config) return config; // already loaded
    const response = await fetch('/config/config.json');
    config = await response.json();
    // Merge with default external services if not provided
    config.externalServices = {
      ...defaultExternalServices,
      ...config.externalServices,
    };
    return config;
  };
  
  export const getConfig = (): AppConfig => {
    if (!config) {
      throw new Error('Configuration not loaded yet');
    }
    return config;
  };
  