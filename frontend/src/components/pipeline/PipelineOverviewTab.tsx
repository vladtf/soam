import React from 'react';
import { Card, Row, Col, Badge } from 'react-bootstrap';
import { SensorData, Device, NormalizationRule, ComputationDef } from '../../api/backendRequests';

interface PipelineOverviewTabProps {
  sensorData: SensorData[];
  devices: Device[];
  filteredRules: NormalizationRule[];
  relatedComputations: ComputationDef[];
  computations: ComputationDef[];
  activePartition: string;
  partitions: string[];
  tableColumns: string[];
}

const PipelineOverviewTab: React.FC<PipelineOverviewTabProps> = ({
  sensorData,
  devices,
  filteredRules,
  relatedComputations,
  computations,
  activePartition,
  partitions,
  tableColumns,
}) => {
  return (
    <Card>
      <Card.Header>
        <h5>📊 Pipeline Overview</h5>
        <small className="text-muted">Real-time view of your data processing pipeline</small>
      </Card.Header>
      <Card.Body>
        <Row className="mb-4">
          <Col md={3}>
            <Card className="text-center border-primary">
              <Card.Body>
                <div className="display-6 text-primary">{sensorData.length}</div>
                <small className="text-muted">Live Records</small>
                <div className="mt-1">
                  <Badge bg="secondary">
                    {activePartition || 'All partitions'}
                  </Badge>
                </div>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center border-success">
              <Card.Body>
                <div className="display-6 text-success">{devices.filter(d => d.enabled).length}</div>
                <small className="text-muted">Active Devices</small>
                <div className="mt-1">
                  <Badge bg="secondary">
                    {devices.length} total
                  </Badge>
                </div>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center border-info">
              <Card.Body>
                <div className="display-6 text-info">{filteredRules.filter(r => r.enabled).length}</div>
                <small className="text-muted">Active Rules</small>
                <div className="mt-1">
                  <Badge bg="secondary">
                    {filteredRules.length} total
                  </Badge>
                </div>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center border-warning">
              <Card.Body>
                <div className="display-6 text-warning">{relatedComputations.length}</div>
                <small className="text-muted">Computations</small>
                <div className="mt-1">
                  <Badge bg="secondary">
                    {computations.length} total
                  </Badge>
                </div>
              </Card.Body>
            </Card>
          </Col>
        </Row>
        
        <Row>
          <Col md={8}>
            <h6>🔄 Data Processing Pipeline</h6>
            <div className="pipeline-flow">
              <div className="d-flex flex-column gap-3">
                <div className="p-3 border rounded bg-body-secondary d-flex align-items-center">
                  <div className="me-3">📡</div>
                  <div className="flex-grow-1">
                    <strong>Raw Data Ingestion</strong>
                    <div className="small text-muted">MQTT → Buffer → MinIO</div>
                  </div>
                  <Badge bg={sensorData.length > 0 ? 'success' : 'secondary'}>
                    {sensorData.length > 0 ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div className="text-center">↓</div>
                <div className="p-3 border rounded bg-body-secondary d-flex align-items-center">
                  <div className="me-3">🔧</div>
                  <div className="flex-grow-1">
                    <strong>Normalization Rules</strong>
                    <div className="small text-muted">Column mapping & cleanup</div>
                  </div>
                  <Badge bg={filteredRules.filter(r => r.enabled).length > 0 ? 'success' : 'secondary'}>
                    {filteredRules.filter(r => r.enabled).length} rules
                  </Badge>
                </div>
                <div className="text-center">↓</div>
                <div className="p-3 border rounded bg-body-secondary d-flex align-items-center">
                  <div className="me-3">⚡</div>
                  <div className="flex-grow-1">
                    <strong>Stream Processing</strong>
                    <div className="small text-muted">Spark enrichment & aggregation</div>
                  </div>
                  <Badge bg="info">Processing</Badge>
                </div>
                <div className="text-center">↓</div>
                <div className="p-3 border rounded bg-body-secondary d-flex align-items-center">
                  <div className="me-3">📊</div>
                  <div className="flex-grow-1">
                    <strong>Computations</strong>
                    <div className="small text-muted">Custom analytics & insights</div>
                  </div>
                  <Badge bg={relatedComputations.length > 0 ? 'success' : 'secondary'}>
                    {relatedComputations.length} active
                  </Badge>
                </div>
              </div>
            </div>
          </Col>
          <Col md={4}>
            <h6>📈 Quick Insights</h6>
            <div className="small">
              <div className="p-2 mb-2 bg-body-tertiary rounded">
                <strong>Data Sources:</strong>
                <div>
                  {partitions.length > 0 ? (
                    partitions.map(p => (
                      <Badge key={p} bg="outline-secondary" className="me-1 mt-1">
                        {p}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted">No partitions available</span>
                  )}
                </div>
              </div>
              
              {sensorData.length > 0 && (
                <div className="p-2 mb-2 bg-body-tertiary rounded">
                  <strong>Latest Data Columns:</strong>
                  <div>
                    {tableColumns.slice(0, 6).map(col => (
                      <Badge key={col} bg="outline-info" className="me-1 mt-1" style={{ fontSize: '0.7rem' }}>
                        {col}
                      </Badge>
                    ))}
                    {tableColumns.length > 6 && (
                      <span className="text-muted">... +{tableColumns.length - 6} more</span>
                    )}
                  </div>
                </div>
              )}
              
              <div className="p-2 mb-2 bg-body-tertiary rounded">
                <strong>System Health:</strong>
                <div className="mt-1">
                  <div className="d-flex justify-content-between">
                    <span>Data Flow:</span>
                    <Badge bg={sensorData.length > 0 ? 'success' : 'warning'}>
                      {sensorData.length > 0 ? 'Active' : 'Stopped'}
                    </Badge>
                  </div>
                  <div className="d-flex justify-content-between">
                    <span>Devices:</span>
                    <Badge bg={devices.filter(d => d.enabled).length > 0 ? 'success' : 'secondary'}>
                      {devices.filter(d => d.enabled).length}/{devices.length}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  );
};

export default PipelineOverviewTab;
