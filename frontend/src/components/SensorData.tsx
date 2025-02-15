import React from 'react';

interface SensorDataProps {
  data: {
    temperature?: number;
    humidity?: number;
  };
}

const SensorData: React.FC<SensorDataProps> = ({ data }) => {
  return (
    <div>
      <p>Temperature: {data.temperature !== undefined ? data.temperature : 'N/A'}</p>
      <p>Humidity: {data.humidity !== undefined ? data.humidity : 'N/A'}</p>
    </div>
  );
};

export default SensorData;
