import React from 'react';
import { Card, Row, Col, Badge, Button } from 'react-bootstrap';

interface PipelineOverviewProps {
  activePartition: string;
  partitions: string[];
  sensorDataCount: number;
  devicesCount: number;
  rulesCount: number;
  computationsCount: number;
  onRefresh: () => void;
}

const PipelineOverview: React.FC<PipelineOverviewProps> = ({
  activePartition,
  partitions,
  sensorDataCount,
  devicesCount,
  rulesCount,
  computationsCount,
  onRefresh,
}) => {
  return (
    <Card>
      <Card.Header className="d-flex justify-content-between align-items-center">
        <h5 className="mb-0">Pipeline Status</h5>
        <Button variant="outline-primary" size="sm" onClick={onRefresh}>
          🔄 Refresh
        </Button>
      </Card.Header>
      <Card.Body>
        <Row>
          <Col md={3}>
            <div className="text-center p-3 border rounded">
              <h3 className="text-primary">{sensorDataCount}</h3>
              <small className="text-muted">Live Data Points</small>
            </div>
          </Col>
          <Col md={3}>
            <div className="text-center p-3 border rounded">
              <h3 className="text-success">{devicesCount}</h3>
              <small className="text-muted">Registered Devices</small>
            </div>
          </Col>
          <Col md={3}>
            <div className="text-center p-3 border rounded">
              <h3 className="text-warning">{rulesCount}</h3>
              <small className="text-muted">Normalization Rules</small>
            </div>
          </Col>
          <Col md={3}>
            <div className="text-center p-3 border rounded">
              <h3 className="text-info">{computationsCount}</h3>
              <small className="text-muted">Active Computations</small>
            </div>
          </Col>
        </Row>
        
        <Row className="mt-3">
          <Col>
            <div className="d-flex flex-wrap gap-2">
              <Badge bg="secondary">
                Active Partition: {activePartition || 'All'}
              </Badge>
              <Badge bg="light" text="dark">
                Total Partitions: {partitions.length}
              </Badge>
            </div>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  );
};

export default PipelineOverview;
