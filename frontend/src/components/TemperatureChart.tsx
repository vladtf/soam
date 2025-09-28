import React from 'react';
import { Card } from 'react-bootstrap';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { FaThermometerHalf } from 'react-icons/fa';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';
import { formatDisplayValue, roundNumericValue } from '../utils/numberUtils';

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
  lastUpdated?: Date | null;
  refreshInterval?: number; // Add refreshInterval prop
}

const TemperatureChart: React.FC<TemperatureChartProps> = ({ 
  data, 
  loading, 
  timeRange, 
  onTimeRangeChange,
  lastUpdated,
  refreshInterval = 15000 // Default to 15000ms if not provided
}) => {
  // Ensure data is sorted chronologically by time_start and round ALL numeric values
  const sortedData = React.useMemo(() => {
    return [...data].sort((a, b) => {
      const timeA = new Date(a.time_start).getTime();
      const timeB = new Date(b.time_start).getTime();
      return timeA - timeB; // Sort ascending (oldest to newest)
    }).map((item) => {
      const roundedItem: any = {};
      Object.keys(item as any).forEach(key => {
        roundedItem[key] = roundNumericValue((item as any)[key]);
      });
      return roundedItem;
    });
  }, [data]);

  return (
    <Card className="mb-3 shadow-sm border-body h-100 d-flex flex-column">
      <Card.Body className="bg-body-tertiary d-flex flex-column">
        <div className="d-flex justify-content-between align-items-start mb-3">
          <Card.Title className="mb-0">
            <FaThermometerHalf className="me-2" /> Hourly Average Temperature
          </Card.Title>
          {lastUpdated && (
            <div className="small text-body-secondary">
              {formatRelativeTime(lastUpdated)} • {formatRefreshPeriod(refreshInterval)}
            </div>
          )}
        </div>
        {/* Updated select for time range with more options */}
        <div className="mb-3">
          <label htmlFor="tempRangeSelect" className="form-label text-body-secondary">Select Time Range:</label>
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
        <div className="flex-grow-1 d-flex flex-column" style={{ minHeight: '300px', maxHeight: '500px' }}>
          {loading ? (
            <div className="text-body-secondary d-flex align-items-center justify-content-center flex-grow-1">Loading...</div>
          ) : (
            // Use ResponsiveContainer with constrained height
            <div className="flex-grow-1" style={{ minHeight: '300px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={timeRange === 0 ? sortedData : sortedData.slice(-timeRange)}
                >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time_start" // Updated to use time_start
                label={{ value: 'Time', position: 'insideBottomRight', offset: -5, style: { textAnchor: 'end', fontSize: 11 } }}
              />
              <YAxis 
                label={{ value: 'Avg Temp (°C)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 11 } }}
                tickFormatter={(value: any) => formatDisplayValue(value)}
              />
              <Tooltip 
                content={({ active, payload, label }: any) => {
                  if (active && payload && payload.length) {
                    const date = label ? new Date(label).toLocaleString() : label;
                    return (
                      <div className="bg-white border rounded shadow-sm p-2" style={{ fontSize: '12px' }}>
                        <p className="mb-1">{date}</p>
                        {payload.map((entry: any, index: number) => (
                          <p key={index} className="mb-0" style={{ color: entry.color }}>
                            {entry.dataKey === 'avg_temp' ? 'Average Temperature' : entry.dataKey} : {formatDisplayValue(entry.value)}°C
                          </p>
                        ))}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend />
              <Line type="monotone" dataKey="avg_temp" stroke="#8884d8" />
            </LineChart>
          </ResponsiveContainer>
            </div>
          )}
        </div>
      </Card.Body>
    </Card>
  );
};

export default TemperatureChart;
