// src/config.ts
export interface AppConfig {
    backendUrl: string;
    ingestorUrl: string;
  }
  
  let config: AppConfig;
  
  export const loadConfig = async (): Promise<AppConfig> => {
    if (config) return config; // already loaded
    const response = await fetch('/config/config.json');
    config = await response.json();
    return config;
  };
  
  export const getConfig = (): AppConfig => {
    if (!config) {
      throw new Error('Configuration not loaded yet');
    }
    return config;
  };
  