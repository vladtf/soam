import { useState, useEffect } from 'react';
import { 
  fetchAverageTemperature, 
  fetchSparkMasterStatus, 
  fetchTemperatureAlerts, 
  SparkMasterStatus 
} from '../api/backendRequests';
import { useError } from '../context/ErrorContext';

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
  
  // Spark status state
  const [sparkMasterStatus, setSparkMasterStatus] = useState<SparkMasterStatus | null>(null);
  const [loadingSparkStatus, setLoadingSparkStatus] = useState<boolean>(true);
  
  // Temperature alerts state
  const [temperatureAlerts, setTemperatureAlerts] = useState<TemperatureAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(true);
  
  // Time range for temperature data
  const [timeRange, setTimeRange] = useState<number>(24);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Fetch temperature data
  const fetchTemperature = async () => {
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
        console.error("Error fetching average temperature:", error);
        setError(error instanceof Error ? error.message : error);
      } finally {
        if (loading) setLoading(false);
        setLastUpdated(new Date());
      }
    };

  useEffect(() => {
    fetchTemperature();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTemperature, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // Fetch Spark status
  const fetchSparkStatusNow = async () => {
      setLoadingSparkStatus(true);
      try {
        const data = await fetchSparkMasterStatus();
        setSparkMasterStatus(data);
      } catch (error: unknown) {
        console.error("Error fetching Spark master status:", error);
        setError(error instanceof Error ? error.message : error);
      } finally {
        setLoadingSparkStatus(false);
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
      try {
        const data = await fetchTemperatureAlerts();
        setTemperatureAlerts(data as TemperatureAlert[]);
      } catch (error: unknown) {
        console.error("Error fetching temperature alerts:", error);
        setError(error instanceof Error ? error.message : error);
      } finally {
        setLoadingAlerts(false);
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
    
    // Temperature alerts
    temperatureAlerts,
    loadingAlerts
  };
};
