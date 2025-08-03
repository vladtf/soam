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

  // Fetch temperature data
  useEffect(() => {
    const fetchData = async () => {
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
        if (loading) setLoading(false); // Only stop loading indicator after the first load
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 15000); // Refresh every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [averageTemperature, loading, setError]);

  // Fetch Spark status
  useEffect(() => {
    const fetchSparkStatus = async () => {
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

    fetchSparkStatus();
    const interval = setInterval(fetchSparkStatus, 15000); // Fetch every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [setError]);

  // Fetch temperature alerts
  useEffect(() => {
    const fetchAlerts = async () => {
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

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 15000); // Poll every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [setError]);

  return {
    // Temperature data
    averageTemperature,
    loading,
    timeRange,
    setTimeRange,
    
    // Spark status
    sparkMasterStatus,
    loadingSparkStatus,
    
    // Temperature alerts
    temperatureAlerts,
    loadingAlerts
  };
};
