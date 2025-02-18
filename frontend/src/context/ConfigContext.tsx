import React, { createContext, useState, useEffect, ReactNode } from 'react';
import { AppConfig, loadConfig } from '../config';

export const ConfigContext = createContext<AppConfig | null>(null);

export const ConfigProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [config, setConfig] = useState<AppConfig | null>(null);

    useEffect(() => {
        loadConfig()
            .then((loadedConfig) => setConfig(loadedConfig))
            .catch((error) => console.error('Error loading config:', error));
    }, []);

    if (!config) {
        return <div>Loading configuration...</div>;
    }

    return (
        <ConfigContext.Provider value={config}>
            {children}
        </ConfigContext.Provider>
    );
};
