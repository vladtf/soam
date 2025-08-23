import React from 'react';
import { Row, Col, Card, Badge, Button } from 'react-bootstrap';
import { SensorData, Device } from '../../api/backendRequests';
import RegisterDeviceCard from '../sensor-data/RegisterDeviceCard';
import DevicesTableCard from '../sensor-data/DevicesTableCard';
import { FaWrench } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';

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
  const navigate = useNavigate();
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
            sensorData={sensorData}
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
                        <Card className="h-100" style={{ fontSize: '0.85rem', minHeight: '200px' }}>
                          <Card.Header className="py-2">
                            <div className="d-flex align-items-center">
                              <Badge 
                                bg={device.enabled ? 'success' : 'secondary'} 
                                className="me-2 flex-shrink-0"
                              >
                                {device.enabled ? '🟢' : '⚪'}
                              </Badge>
                              <div className="flex-grow-1" style={{ minWidth: 0 }}>
                                <div 
                                  className="fw-bold text-truncate" 
                                  title={device.name}
                                >
                                  {device.name}
                                </div>
                                <small 
                                  className="text-muted text-truncate d-block" 
                                  title={device.ingestion_id}
                                >
                                  {device.ingestion_id}
                                </small>
                              </div>
                            </div>
                          </Card.Header>
                          <Card.Body className="py-2 d-flex flex-column">
                            {deviceData.length > 0 ? (
                              <div className="flex-grow-1">
                                <small className="text-muted">Latest: {deviceData.length} records</small>
                                <div className="mt-1">
                                  {Object.entries(deviceData[0] as Record<string, unknown>)
                                    .slice(0, 3)
                                    .map(([key, value]) => (
                                      <div key={key} className="d-flex justify-content-between align-items-start mb-1">
                                        <code 
                                          className="text-truncate me-1" 
                                          style={{ fontSize: '0.7rem', maxWidth: '40%', flex: '0 0 auto' }}
                                          title={key}
                                        >
                                          {key}:
                                        </code>
                                        <span 
                                          className="text-truncate text-end" 
                                          style={{ fontSize: '0.7rem', maxWidth: '60%', flex: '1 1 auto' }}
                                          title={renderValue(value)}
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
      
      {/* Troubleshooting Tools Link */}
      <Row className="mt-3">
        <Col>
          <Card className="shadow-sm border-primary border-opacity-25">
            <Card.Body className="text-center py-3">
              <h6 className="mb-2">
                <FaWrench className="me-2 text-primary" />
                Need to troubleshoot data pipeline issues?
              </h6>
              <p className="text-muted mb-3 small">
                Access comprehensive diagnostic tools for data enrichment, field-level troubleshooting, and system monitoring.
              </p>
              <Button 
                variant="primary" 
                size="sm" 
                onClick={() => navigate('/troubleshooting')}
              >
                <FaWrench className="me-1" />
                Open Troubleshooting Tools
              </Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default DevicesTab;
