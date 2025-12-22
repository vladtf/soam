import React, { useState } from 'react';
import { Card, ListGroup, Button } from 'react-bootstrap';
import { FaBell, FaCog } from 'react-icons/fa';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';
import { formatDisplayValue } from '../utils/numberUtils';
import TemperatureThresholdModal from './TemperatureThresholdModal';

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
  onRefresh?: () => void; // Add callback for manual refresh
}

const TemperatureAlertsCard: React.FC<TemperatureAlertsCardProps> = ({ 
  alerts, 
  loading, 
  lastUpdated, 
  refreshInterval = 15000,
  onRefresh
}) => {
  const [showModal, setShowModal] = useState(false);

  const handleSettingsClick = () => {
    setShowModal(true);
  };

  const handleModalClose = () => {
    setShowModal(false);
  };

  const handleThresholdUpdate = () => {
    // Refresh data when threshold is updated
    if (onRefresh) {
      onRefresh();
    }
  };
  return (
    <>
      <Card className="mb-3 shadow-sm border-body h-100 d-flex flex-column">
        <Card.Body className="bg-body-tertiary d-flex flex-column">
          <div className="d-flex justify-content-between align-items-start mb-2">
            <Card.Title className="mb-0">
              <FaBell className="me-2" /> Temperature Alerts
            </Card.Title>
            <div className="d-flex align-items-center gap-2">
              {lastUpdated && (
                <div className="small text-body-secondary">
                  {formatRelativeTime(lastUpdated)} • {formatRefreshPeriod(refreshInterval)}
                </div>
              )}
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={handleSettingsClick}
                title="Configure temperature threshold"
              >
                <FaCog />
              </Button>
            </div>
          </div>
          <div className="flex-grow-1 d-flex flex-column">
            {loading ? (
              <div className="text-body-secondary d-flex align-items-center justify-content-center flex-grow-1">Loading...</div>
            ) : alerts.length > 0 ? (
              <div className="flex-grow-1" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                <ListGroup variant="flush">
                  {alerts.map((alert, index) => (
                    <ListGroup.Item key={index}>
                      <strong>Sensor:</strong> {alert.sensorId} |{' '}
                      <strong>Temp:</strong> {formatDisplayValue(alert.temperature)}°C |{' '}
                      <strong>Time:</strong> <span className="text-body-secondary">{alert.event_time}</span>
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </div>
            ) : (
              <div className="text-body-secondary d-flex align-items-center justify-content-center flex-grow-1">No alerts found.</div>
            )}
          </div>
        </Card.Body>
      </Card>

      <TemperatureThresholdModal 
        show={showModal}
        onHide={handleModalClose}
        onUpdate={handleThresholdUpdate}
      />
    </>
  );
};

export default TemperatureAlertsCard;
