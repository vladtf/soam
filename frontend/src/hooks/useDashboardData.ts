import { useState, useEffect } from 'react';
import { 
  fetchAverageTemperature, 
  fetchSparkMasterStatus, 
  fetchTemperatureAlerts, 
  SparkMasterStatus 
} from '../api/backendRequests';
import { useError } from '../context/ErrorContext';
import { reportClientError } from '../errors';

interface TemperatureData {
  time_start: string;
  avg_temp: number;
  sensorId: string;
}

interface TemperatureAlert {
  sensorId: string;
  temperature: number;
  event_time: string;
}

export const useDashboardData = () => {
  const { setError } = useError();
  
  // Temperature data state
  const [averageTemperature, setAverageTemperature] = useState<TemperatureData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshingTemperature, setRefreshingTemperature] = useState<boolean>(false);
  
  // Spark status state
  const [sparkMasterStatus, setSparkMasterStatus] = useState<SparkMasterStatus | null>(null);
  const [loadingSparkStatus, setLoadingSparkStatus] = useState<boolean>(true);
  const [refreshingSparkStatus, setRefreshingSparkStatus] = useState<boolean>(false);
  
  // Temperature alerts state
  const [temperatureAlerts, setTemperatureAlerts] = useState<TemperatureAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(true);
  const [refreshingAlerts, setRefreshingAlerts] = useState<boolean>(false);
  
  // Time range for temperature data
  const [timeRange, setTimeRange] = useState<number>(24);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Fetch temperature data
  const fetchTemperature = async () => {
      const hasExistingData = averageTemperature.length > 0;
      
      if (hasExistingData) {
        setRefreshingTemperature(true);
      } else {
        setLoading(true);
      }
      
      try {
        const data = await fetchAverageTemperature();
        // Format the time_start field for proper display on the X-axis
        const formattedData = (data as TemperatureData[]).map((item) => ({
          ...item,
          time_start: new Date(item.time_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }));
        // Compare new data with the existing state to avoid unnecessary updates
        if (JSON.stringify(formattedData) !== JSON.stringify(averageTemperature)) {
          setAverageTemperature(formattedData);
        }
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchTemperature' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoading(false);
        setRefreshingTemperature(false);
        setLastUpdated(new Date());
      }
    };

  useEffect(() => {
    fetchTemperature();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTemperature, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchTemperature]);

  // Fetch Spark status
  const fetchSparkStatusNow = async () => {
      const hasExistingData = sparkMasterStatus !== null;
      
      if (hasExistingData) {
        setRefreshingSparkStatus(true);
      } else {
        setLoadingSparkStatus(true);
      }
      
      try {
        const data = await fetchSparkMasterStatus();
        setSparkMasterStatus(data);
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchSparkStatusNow' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoadingSparkStatus(false);
        setRefreshingSparkStatus(false);
      }
    };

  useEffect(() => {
    fetchSparkStatusNow();
    if (!autoRefresh) return;
    const interval = setInterval(fetchSparkStatusNow, 15000);
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [setError, autoRefresh]);

  // Fetch temperature alerts
  const fetchAlertsNow = async () => {
      const hasExistingData = temperatureAlerts.length > 0;
      
      if (hasExistingData) {
        setRefreshingAlerts(true);
      } else {
        setLoadingAlerts(true);
      }
      
      try {
        const data = await fetchTemperatureAlerts();
        setTemperatureAlerts(data as TemperatureAlert[]);
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : error);
        reportClientError({ message: String(error), severity: 'error', component: 'useDashboardData', context: 'fetchAlertsNow' }).catch(() => {});
        // Don't clear existing data on error if we have it
      } finally {
        setLoadingAlerts(false);
        setRefreshingAlerts(false);
      }
    };

  useEffect(() => {
    fetchAlertsNow();
    if (!autoRefresh) return;
    const interval = setInterval(fetchAlertsNow, 15000);
    return () => clearInterval(interval);
  }, [setError, autoRefresh]);

  return {
    // Temperature data
    averageTemperature,
    loading,
    refreshingTemperature,
    timeRange,
    setTimeRange,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refreshAll: async () => {
      await Promise.all([
        fetchTemperature(),
        fetchSparkStatusNow(),
        fetchAlertsNow(),
      ]);
      setLastUpdated(new Date());
    },
    
    // Spark status
    sparkMasterStatus,
    loadingSparkStatus,
    refreshingSparkStatus,
    
    // Temperature alerts
    temperatureAlerts,
    loadingAlerts,
    refreshingAlerts
  };
};
