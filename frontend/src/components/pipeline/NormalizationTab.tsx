import React from 'react';
import { Row, Col, Card, Badge } from 'react-bootstrap';
import { SensorData, NormalizationRule } from '../../api/backendRequests';
import NormalizationRulesSection from './NormalizationRulesSection';

interface NormalizationTabProps {
  filteredRules: NormalizationRule[];
  activePartition: string;
  partitions: string[];
  onRulesChange: () => void;
  sampleData: SensorData[];
  tableColumns: string[];
  renderValue: (v: unknown) => string;
}

const NormalizationTab: React.FC<NormalizationTabProps> = ({
  filteredRules,
  activePartition,
  partitions,
  onRulesChange,
  sampleData,
  tableColumns,
  renderValue,
}) => {
  return (
    <Row>
      <Col lg={8}>
        <NormalizationRulesSection
          rules={filteredRules}
          activePartition={activePartition}
          partitions={partitions}
          onRulesChange={onRulesChange}
          sampleData={sampleData}
        />
      </Col>
      <Col lg={4}>
        <Card className="h-100">
          <Card.Header>
            <h6 className="mb-0">📋 Data Sample</h6>
            <small className="text-muted">
              Recent columns from {activePartition || 'all partitions'}
            </small>
          </Card.Header>
          <Card.Body style={{ maxHeight: '500px', overflowY: 'auto' }}>
            {sampleData.length > 0 ? (
              <div>
                <p className="small text-muted mb-2">
                  Available columns in your data:
                </p>
                <div className="mb-3">
                  {tableColumns.map((col) => (
                    <Badge 
                      key={col} 
                      bg="secondary" 
                      className="me-1 mb-1"
                      style={{ fontSize: '0.8rem' }}
                    >
                      {col}
                    </Badge>
                  ))}
                </div>
                <hr />
                <p className="small text-muted mb-2">Sample values:</p>
                <div style={{ fontSize: '0.85rem' }}>
                  {sampleData.slice(0, 3).map((row, idx) => (
                    <div key={idx} className="p-2 mb-2 bg-body-tertiary rounded">
                      {Object.entries(row as Record<string, unknown>)
                        .slice(0, 4)
                        .map(([key, value]) => (
                          <div key={key} className="d-flex justify-content-between">
                            <code className="text-primary">{key}:</code>
                            <span className="text-truncate ms-2" style={{ maxWidth: '120px' }}>
                              {renderValue(value)}
                            </span>
                          </div>
                        ))}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center text-muted py-4">
                <p>No data available</p>
                <small>Ingest some sensor data to see column structures</small>
              </div>
            )}
          </Card.Body>
        </Card>
      </Col>
    </Row>
  );
};

export default NormalizationTab;
