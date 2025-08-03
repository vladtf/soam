import React from 'react';
import { Card } from 'react-bootstrap';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { FaThermometerHalf } from 'react-icons/fa';

interface TemperatureData {
  time_start: string;
  avg_temp: number;
  sensorId: string;
}

interface TemperatureChartProps {
  data: TemperatureData[];
  loading: boolean;
  timeRange: number;
  onTimeRangeChange: (range: number) => void;
}

const TemperatureChart: React.FC<TemperatureChartProps> = ({ 
  data, 
  loading, 
  timeRange, 
  onTimeRangeChange 
}) => {
  return (
    <Card className="mb-3">
      <Card.Body>
        <Card.Title>
          <FaThermometerHalf className="me-2" /> Hourly Average Temperature
        </Card.Title>
        {/* Updated select for time range with more options */}
        <div className="mb-3">
          <label htmlFor="tempRangeSelect" className="form-label">Select Time Range:</label>
          <select
            id="tempRangeSelect"
            value={timeRange}
            onChange={e => onTimeRangeChange(Number(e.target.value))}
            className="form-select"
          >
            <option value={5}>Last 5 minutes</option>
            <option value={15}>Last 15 minutes</option>
            <option value={30}>Last 30 minutes</option>
            <option value={60}>Last 1 hour</option>
            <option value={120}>Last 2 hours</option>
            <option value={0}>All</option>
          </select>
        </div>
        {loading ? (
          <div>Loading...</div>
        ) : (
          // Use ResponsiveContainer to fill the entire card
          <ResponsiveContainer width="100%" height={400}>
            <LineChart
              data={timeRange === 0 ? data : data.slice(-timeRange)}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time_start" // Updated to use time_start
                label={{ value: 'Time', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis label={{ value: 'Avg Temp (°C)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="avg_temp" stroke="#8884d8" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card.Body>
    </Card>
  );
};

export default TemperatureChart;
