import React from 'react';
import { Card, ListGroup } from 'react-bootstrap';
import { FaBell } from 'react-icons/fa';

interface TemperatureAlert {
  sensorId: string;
  temperature: number;
  event_time: string;
}

interface TemperatureAlertsCardProps {
  alerts: TemperatureAlert[];
  loading: boolean;
}

const TemperatureAlertsCard: React.FC<TemperatureAlertsCardProps> = ({ alerts, loading }) => {
  return (
    <Card className="mb-3 shadow-sm border-body">
      <Card.Body className="bg-body-tertiary">
        <Card.Title>
          <FaBell className="me-2" /> Temperature Alerts
        </Card.Title>
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
