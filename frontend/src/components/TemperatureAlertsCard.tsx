import React from 'react';
import { Card, ListGroup } from 'react-bootstrap';
import { FaBell } from 'react-icons/fa';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';

interface TemperatureAlert {
  sensorId: string;
  temperature: number;
  event_time: string;
}

interface TemperatureAlertsCardProps {
  alerts: TemperatureAlert[];
  loading: boolean;
  lastUpdated?: Date | null;
  refreshInterval?: number; // in milliseconds
}

const TemperatureAlertsCard: React.FC<TemperatureAlertsCardProps> = ({ alerts, loading, lastUpdated, refreshInterval = 15000 }) => {
  return (
    <Card className="mb-3 shadow-sm border-body">
      <Card.Body className="bg-body-tertiary">
        <div className="d-flex justify-content-between align-items-start mb-2">
          <Card.Title className="mb-0">
            <FaBell className="me-2" /> Temperature Alerts
          </Card.Title>
          {lastUpdated && (
            <div className="small text-body-secondary">
              {formatRelativeTime(lastUpdated)} • {formatRefreshPeriod(refreshInterval)}
            </div>
          )}
        </div>
        {loading ? (
          <div className="text-body-secondary">Loading...</div>
        ) : alerts.length > 0 ? (
          <ListGroup variant="flush">
            {alerts.map((alert, index) => (
              <ListGroup.Item key={index}>
                <strong>Sensor:</strong> {alert.sensorId} |{' '}
                <strong>Temp:</strong> {alert.temperature}°C |{' '}
                <strong>Time:</strong> <span className="text-body-secondary">{alert.event_time}</span>
              </ListGroup.Item>
            ))}
          </ListGroup>
        ) : (
          <div className="text-body-secondary">No alerts found.</div>
        )}
      </Card.Body>
    </Card>
  );
};

export default TemperatureAlertsCard;
