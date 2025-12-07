import React, { useState } from 'react';
import { Row, Col, Card, Badge, Button, Modal, Table } from 'react-bootstrap';
import { SensorData, Device, DataSensitivity } from '../../api/backendRequests';
import RegisterDeviceCard from '../sensor-data/RegisterDeviceCard';
import DevicesTableCard from '../sensor-data/DevicesTableCard';
import { FaShieldAlt, FaTimes } from 'react-icons/fa';

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
  sensitivity: DataSensitivity;
  setSensitivity: (sensitivity: DataSensitivity) => void;
  dataRetentionDays: number;
  setDataRetentionDays: (days: number) => void;
  onRegister: (e: React.FormEvent) => void;
  onToggle: (id: number) => void;
  onDelete: (id: number) => void;
  renderValue: (v: unknown) => string;
  isAdmin?: boolean;
}

const SENSITIVITY_COLORS: Record<DataSensitivity, string> = {
  public: 'success',
  internal: 'info',
  confidential: 'warning',
  restricted: 'danger',
};

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
  sensitivity,
  setSensitivity,
  dataRetentionDays,
  setDataRetentionDays,
  onRegister,
  onToggle,
  onDelete,
  renderValue,
  isAdmin = false,
}) => {
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [showModal, setShowModal] = useState(false);

  const handleDeviceClick = (device: Device) => {
    setSelectedDevice(device);
    setShowModal(true);
  };

  const getDeviceData = (device: Device) => {
    return sensorData.filter((data: SensorData) =>
      data.ingestion_id === device.ingestion_id ||
      (data as Record<string, unknown>).sensorId === device.name ||
      (data as Record<string, unknown>).sensor_id === device.name
    );
  };

  return (
    <>
      {/* Device Details Modal */}
      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            <FaShieldAlt className="me-2" />
            Device Details
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedDevice && (
            <>
              <Row className="mb-3">
                <Col md={6}>
                  <h6 className="text-muted mb-1">Device Name</h6>
                  <p className="fw-bold mb-2" style={{ wordBreak: 'break-word' }}>
                    {selectedDevice.name || 'Unnamed Device'}
                  </p>

                  <h6 className="text-muted mb-1">Ingestion ID</h6>
                  <p className="mb-2" style={{ wordBreak: 'break-all' }}>
                    <code style={{ fontSize: '0.8rem' }}>{selectedDevice.ingestion_id}</code>
                  </p>

                  <h6 className="text-muted mb-1">Description</h6>
                  <p className="mb-2">{selectedDevice.description || 'No description'}</p>
                </Col>
                <Col md={6}>
                  <h6 className="text-muted mb-1">Status</h6>
                  <p className="mb-2">
                    <Badge bg={selectedDevice.enabled ? 'success' : 'secondary'}>
                      {selectedDevice.enabled ? '🟢 Active' : '⚪ Inactive'}
                    </Badge>
                  </p>

                  <h6 className="text-muted mb-1">Sensitivity</h6>
                  <p className="mb-2">
                    <Badge bg={SENSITIVITY_COLORS[selectedDevice.sensitivity || 'internal']}>
                      <FaShieldAlt className="me-1" size={10} />
                      {(selectedDevice.sensitivity || 'internal').charAt(0).toUpperCase() +
                        (selectedDevice.sensitivity || 'internal').slice(1)}
                    </Badge>
                  </p>

                  <h6 className="text-muted mb-1">Data Retention</h6>
                  <p className="mb-2">{selectedDevice.data_retention_days || 90} days</p>

                  <h6 className="text-muted mb-1">Created</h6>
                  <p className="mb-2">
                    {selectedDevice.created_at
                      ? new Date(selectedDevice.created_at).toLocaleString()
                      : 'Unknown'}
                    {selectedDevice.created_by && (
                      <Badge bg="info" className="ms-2 text-dark">{selectedDevice.created_by}</Badge>
                    )}
                  </p>
                </Col>
              </Row>

              <hr />

              <h6 className="mb-3">📊 Recent Data ({getDeviceData(selectedDevice).length} records)</h6>
              {getDeviceData(selectedDevice).length > 0 ? (
                <div style={{ maxHeight: '300px', overflow: 'auto' }}>
                  <Table size="sm" striped bordered hover>
                    <thead className="sticky-top bg-light">
                      <tr>
                        {Object.keys(getDeviceData(selectedDevice)[0] as Record<string, unknown>).map((key) => (
                          <th key={key} style={{ fontSize: '0.8rem' }}>{key}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {getDeviceData(selectedDevice).slice(0, 10).map((data, idx) => (
                        <tr key={idx}>
                          {Object.values(data as Record<string, unknown>).map((value, vIdx) => (
                            <td key={vIdx} style={{ fontSize: '0.75rem', maxWidth: '150px' }} className="text-truncate" title={renderValue(value)}>
                              {renderValue(value)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              ) : (
                <p className="text-muted text-center">No recent data available for this device</p>
              )}
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>
            <FaTimes className="me-1" /> Close
          </Button>
        </Modal.Footer>
      </Modal>

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
            sensitivity={sensitivity}
            setSensitivity={setSensitivity}
            dataRetentionDays={dataRetentionDays}
            setDataRetentionDays={setDataRetentionDays}
            onRegister={onRegister}
            sensorData={sensorData}
            isAdmin={isAdmin}
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
                    const deviceData = getDeviceData(device);
                    const sensitivityColor = SENSITIVITY_COLORS[device.sensitivity || 'internal'];
                    return (
                      <Col md={6} lg={3} key={device.id} className="mb-3">
                        <Card
                          className="h-100"
                          style={{ fontSize: '0.85rem', minHeight: '200px', cursor: 'pointer' }}
                          onClick={() => handleDeviceClick(device)}
                        >
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
                              <Badge
                                bg={sensitivityColor}
                                className="ms-1 flex-shrink-0"
                                title={`Sensitivity: ${device.sensitivity || 'internal'}`}
                              >
                                <FaShieldAlt size={10} />
                              </Badge>
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
                                <small className="text-primary mt-2 d-block">Click for details →</small>
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
