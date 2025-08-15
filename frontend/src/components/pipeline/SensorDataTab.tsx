import React from 'react';
import { Row, Col, Card } from 'react-bootstrap';
import { SensorData } from '../../api/backendRequests';
import DataViewer from '../sensor-data/DataViewer';

interface SensorDataTabProps {
  sensorData: SensorData[];
  activePartition: string;
  viewMode: 'table' | 'json';
  tableColumns: string[];
  renderValue: (v: unknown) => string;
}

const SensorDataTab: React.FC<SensorDataTabProps> = ({
  sensorData,
  activePartition,
  viewMode,
  tableColumns,
  renderValue,
}) => {
  return (
    <>
      <Row className="mb-3">
        <Col>
          <Card>
            <Card.Header>
              <h6 className="mb-0">📊 Data Summary</h6>
              <small className="text-muted">
                Live sensor data from {activePartition || 'all partitions'}
              </small>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col md={3}>
                  <div className="text-center">
                    <div className="display-6 text-primary">{sensorData.length}</div>
                    <small className="text-muted">Records</small>
                  </div>
                </Col>
                <Col md={3}>
                  <div className="text-center">
                    <div className="display-6 text-success">{tableColumns.length}</div>
                    <small className="text-muted">Columns</small>
                  </div>
                </Col>
                <Col md={3}>
                  <div className="text-center">
                    <div className="display-6 text-info">
                      {new Set(sensorData.map((d: any) => d.ingestion_id)).size}
                    </div>
                    <small className="text-muted">Sources</small>
                  </div>
                </Col>
                <Col md={3}>
                  <div className="text-center">
                    <div className="display-6 text-warning">
                      {new Set(sensorData.map((d: any) => d.sensorId || d.sensor_id)).size}
                    </div>
                    <small className="text-muted">Unique Sensors</small>
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row>
        <Col>
          <DataViewer
            data={sensorData}
            viewMode={viewMode}
            tableColumns={tableColumns}
            renderValue={renderValue}
          />
        </Col>
      </Row>
    </>
  );
};

export default SensorDataTab;
