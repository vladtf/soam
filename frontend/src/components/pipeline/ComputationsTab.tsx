import React from 'react';
import { Row, Col, Card, Badge } from 'react-bootstrap';
import { SensorData, ComputationDef } from '../../api/backendRequests';
import ComputationsSection from './ComputationsSection';

interface ComputationsTabProps {
  relatedComputations: ComputationDef[];
  activePartition: string;
  onComputationsChange: () => void;
  sensorData: SensorData[];
  renderValue: (v: unknown) => string;
}

const ComputationsTab: React.FC<ComputationsTabProps> = ({
  relatedComputations,
  activePartition,
  onComputationsChange,
  sensorData,
  renderValue,
}) => {
  return (
    <Row>
      <Col lg={8}>
        <ComputationsSection
          computations={relatedComputations}
          activePartition={activePartition}
          onComputationsChange={onComputationsChange}
        />
      </Col>
      <Col lg={4}>
        <Card className="h-100">
          <Card.Header>
            <h6 className="mb-0">📊 Data Context</h6>
            <small className="text-muted">
              Available for computations
            </small>
          </Card.Header>
          <Card.Body style={{ maxHeight: '500px', overflowY: 'auto' }}>
            <div className="mb-3">
              <h6 className="small">Data Sources:</h6>
              <Badge bg="info" className="me-1">Gold Dataset</Badge>
              <Badge bg="secondary" className="me-1">Sensors Dataset</Badge>
            </div>
            
            {sensorData.length > 0 && (
              <>
                <h6 className="small">Recent Values:</h6>
                <div style={{ fontSize: '0.85rem' }}>
                  {sensorData.slice(0, 2).map((row, idx) => (
                    <div key={idx} className="p-2 mb-2 border rounded">
                      <div className="small text-muted mb-1">Record {idx + 1}:</div>
                      {Object.entries(row as Record<string, unknown>)
                        .filter(([key]) => ['timestamp', 'temperature', 'humidity', 'sensorId', 'sensor_id'].includes(key))
                        .map(([key, value]) => (
                          <div key={key} className="d-flex justify-content-between">
                            <code className="text-success">{key}:</code>
                            <span className="text-truncate ms-2" style={{ maxWidth: '100px' }}>
                              {renderValue(value)}
                            </span>
                          </div>
                        ))}
                    </div>
                  ))}
                </div>
                
                <hr />
                <div className="small text-muted">
                  <p className="mb-1"><strong>Tips for computations:</strong></p>
                  <ul className="mb-0" style={{ fontSize: '0.8rem' }}>
                    <li>Use <code>SELECT *</code> to see all columns</li>
                    <li>Filter by <code>ingestion_id</code> for specific data</li>
                    <li>Aggregate with <code>AVG()</code>, <code>SUM()</code>, etc.</li>
                  </ul>
                </div>
              </>
            )}
          </Card.Body>
        </Card>
      </Col>
    </Row>
  );
};

export default ComputationsTab;
