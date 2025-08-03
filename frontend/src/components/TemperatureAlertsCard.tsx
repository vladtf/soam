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

const TemperatureAlertsCard: React.FC<TemperatureAlertsCardProps> = ({ 
  alerts, 
  loading 
}) => {
  return (
    <Card className="mb-3">
      <Card.Body>
        <Card.Title>
          <FaBell className="me-2" /> Temperature Alerts
        </Card.Title>
        {loading ? (
          <div>Loading...</div>
        ) : alerts.length > 0 ? (
          <ListGroup variant="flush">
            {alerts.map((alert, index) => (
              <ListGroup.Item key={index}>
                <strong>Sensor:</strong> {alert.sensorId} | 
                <strong> Temp:</strong> {alert.temperature}°C | 
                <strong> Time:</strong> {alert.event_time}
              </ListGroup.Item>
            ))}
          </ListGroup>
        ) : (
          <div>No alerts found.</div>
        )}
      </Card.Body>
    </Card>
  );
};

export default TemperatureAlertsCard;
