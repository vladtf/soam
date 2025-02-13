import { useEffect, useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

interface SensorData {
  temperature?: number;
  humidity?: number;
}


function App() {
  const [data, setData] = useState<SensorData>({});

  const fetchData = async () => {
    try {
      const response = await fetch('http://localhost:8000/data');
      const json = await response.json();
      setData(json);
    } catch (error) {
      console.error('Error fetching sensor data:', error);
    }
  };

  useEffect(() => {
    // Fetch data immediately and then every 5 seconds
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="App">
      <h1>Sensor Data</h1>
      <div>
        <p>Temperature: {data.temperature !== undefined ? data.temperature : 'N/A'}</p>
        <p>Humidity: {data.humidity !== undefined ? data.humidity : 'N/A'}</p>
      </div>
    </div>
  );

}

export default App
