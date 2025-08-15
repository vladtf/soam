import React from 'react';
import { Row, Col, Card, Badge } from 'react-bootstrap';
import { SensorData, Device } from '../../api/backendRequests';
import RegisterDeviceCard from '../sensor-data/RegisterDeviceCard';
import DevicesTableCard from '../sensor-data/DevicesTableCard';

interface DevicesTabProps {
  devices: Device[];
  sensorData: SensorData[];
  activePartition: string;
  ingestionId: string;
  setIngestionId: (id: string) => void;
  name: string;
  setName: (name: string) => void;
  description: string;
  setDescription: (description: string) => void;
  onRegister: (e: React.FormEvent) => void;
  onToggle: (id: number) => void;
  onDelete: (id: number) => void;
  renderValue: (v: unknown) => string;
}

const DevicesTab: React.FC<DevicesTabProps> = ({
  devices,
  sensorData,
  activePartition,
  ingestionId,
  setIngestionId,
  name,
  setName,
  description,
  setDescription,
  onRegister,
  onToggle,
  onDelete,
  renderValue,
}) => {
  return (
    <>
      <Row>
        <Col lg={6}>
          <RegisterDeviceCard
            activePartition={activePartition}
            ingestionId={ingestionId}
            setIngestionId={setIngestionId}
            name={name}
            setName={setName}
            description={description}
            setDescription={setDescription}
            onRegister={onRegister}
          />
        </Col>
        <Col lg={6}>
          <DevicesTableCard
            devices={devices}
            onToggle={onToggle}
            onDelete={onDelete}
          />
        </Col>
      </Row>
      <Row className="mt-3">
        <Col>
          <Card>
            <Card.Header>
              <h6 className="mb-0">🔍 Device Data Preview</h6>
              <small className="text-muted">
                Recent data from registered devices
              </small>
            </Card.Header>
            <Card.Body>
              {devices.length > 0 && sensorData.length > 0 ? (
                <Row>
                  {devices.slice(0, 4).map((device) => {
                    const deviceData = sensorData.filter((data: any) => 
                      data.ingestion_id === device.ingestion_id || 
                      data.sensorId === device.name ||
                      data.sensor_id === device.name
                    );
                    return (
                      <Col md={6} lg={3} key={device.id} className="mb-3">
                        <Card className="h-100" style={{ fontSize: '0.85rem' }}>
                          <Card.Header className="py-2">
                            <div className="d-flex align-items-center">
                              <Badge 
                                bg={device.enabled ? 'success' : 'secondary'} 
                                className="me-2"
                              >
                                {device.enabled ? '🟢' : '⚪'}
                              </Badge>
                              <div>
                                <div className="fw-bold">{device.name}</div>
                                <small className="text-muted">{device.ingestion_id}</small>
                              </div>
                            </div>
                          </Card.Header>
                          <Card.Body className="py-2">
                            {deviceData.length > 0 ? (
                              <div>
                                <small className="text-muted">Latest: {deviceData.length} records</small>
                                <div className="mt-1">
                                  {Object.entries(deviceData[0] as Record<string, unknown>)
                                    .slice(0, 3)
                                    .map(([key, value]) => (
                                      <div key={key} className="d-flex justify-content-between">
                                        <code style={{ fontSize: '0.7rem' }}>{key}:</code>
                                        <span 
                                          className="text-truncate ms-1" 
                                          style={{ maxWidth: '80px', fontSize: '0.7rem' }}
                                        >
                                          {renderValue(value)}
                                        </span>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            ) : (
                              <small className="text-muted">No recent data</small>
                            )}
                          </Card.Body>
                        </Card>
                      </Col>
                    );
                  })}
                </Row>
              ) : (
                <div className="text-center text-muted py-3">
                  <p>No registered devices or data available</p>
                  <small>Register devices and start ingesting data to see previews</small>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default DevicesTab;
