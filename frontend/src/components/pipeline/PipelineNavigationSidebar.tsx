import React from 'react';
import { Nav, Card, Badge } from 'react-bootstrap';
import { SensorData, Device, NormalizationRule, ComputationDef, ValueTransformationRule } from '../../api/backendRequests';

interface PipelineNavigationSidebarProps {
  sensorData: SensorData[];
  devices: Device[];
  filteredRules: NormalizationRule[];
  valueTransformationRules: ValueTransformationRule[];
  relatedComputations: ComputationDef[];
}

const PipelineNavigationSidebar: React.FC<PipelineNavigationSidebarProps> = ({
  sensorData,
  devices,
  filteredRules,
  valueTransformationRules,
  relatedComputations,
}) => {
  return (
    <div className="sticky-top" style={{ top: '20px' }}>
      <Card className="mb-3">
        <Card.Header>
          <h6 className="mb-0">Pipeline Navigation</h6>
        </Card.Header>
        <Card.Body className="p-2">
          <Nav variant="pills" className="flex-column">
            <Nav.Item>
              <Nav.Link
                eventKey="devices"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>🔌 Devices</span>
                <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>{devices.length}</Badge>
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                eventKey="sensors"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>📡 Data</span>
                <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>{sensorData.length}</Badge>
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                eventKey="normalization"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>🔧 Normalization</span>
                <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>{filteredRules.length}</Badge>
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                eventKey="value-transformations"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>🔄 Transforms</span>
                <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>{valueTransformationRules.length}</Badge>
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                eventKey="computations"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>⚡ Compute</span>
                <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>{relatedComputations.length}</Badge>
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link
                eventKey="overview"
                className="d-flex align-items-center justify-content-between mb-2 text-nowrap"
                style={{ fontSize: '0.9rem' }}
              >
                <span>📊 Overview</span>
              </Nav.Link>
            </Nav.Item>
          </Nav>
          
          <hr />
          <div className="small text-muted">
            <div className="d-flex align-items-center gap-2 mb-1">
              <Badge bg={sensorData.length > 0 ? 'success' : 'secondary'} style={{ fontSize: '0.7rem' }}>
                {sensorData.length > 0 ? '🟢' : '⚪'}
              </Badge>
              <span>Data flow: {sensorData.length} records</span>
            </div>
            <div className="d-flex align-items-center gap-2">
              <Badge bg={devices.filter(d => d.enabled).length > 0 ? 'success' : 'secondary'} style={{ fontSize: '0.7rem' }}>
                {devices.filter(d => d.enabled).length > 0 ? '🟢' : '⚪'}
              </Badge>
              <span>Active devices: {devices.filter(d => d.enabled).length}/{devices.length}</span>
            </div>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default PipelineNavigationSidebar;
