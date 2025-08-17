import React from 'react';
import { Card, Badge, Row, Col, ProgressBar, Spinner } from 'react-bootstrap';
import { FaTasks, FaServer, FaCog, FaMemory, FaUsers, FaClock } from 'react-icons/fa';
import { SparkMasterStatus, SparkApplication } from '../api/backendRequests';
import { useTheme } from '../context/ThemeContext';
import ThemedTable from './ThemedTable';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';

interface SparkApplicationsCardProps {
  sparkMasterStatus: SparkMasterStatus | null;
  loading: boolean;
  refreshing?: boolean;
  lastUpdated?: Date | null;
  refreshInterval?: number; // in milliseconds
}

const SparkApplicationsCard: React.FC<SparkApplicationsCardProps> = ({ 
  sparkMasterStatus, 
  loading,
  refreshing = false,
  lastUpdated,
  refreshInterval = 15000 // default to 15 seconds if not provided
}) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const getStateVariant = (state: string) => {
    switch (state?.toLowerCase()) {
      case 'running':
        return 'success';
      case 'waiting':
        return 'warning';
      case 'finished':
        return 'info';
      case 'failed':
      case 'killed':
        return 'danger';
      default:
        return 'secondary';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const calculateResourceUtilization = () => {
    if (!sparkMasterStatus) return { cores: 0, memory: 0 };
    
    const coreUtilization = sparkMasterStatus.cores > 0 
      ? (sparkMasterStatus.coresused / sparkMasterStatus.cores) * 100 
      : 0;
    
    const memoryUtilization = sparkMasterStatus.memory > 0 
      ? (sparkMasterStatus.memoryused / sparkMasterStatus.memory) * 100 
      : 0;
    
    return { cores: coreUtilization, memory: memoryUtilization };
  };

  const { cores: coreUtilization, memory: memoryUtilization } = calculateResourceUtilization();

  return (
    <Card className="mb-3 shadow-sm">
      <Card.Header className="bg-primary text-white d-flex align-items-center justify-content-between">
        <div className="d-flex align-items-center">
          <FaTasks className="me-2" />
          <strong>Spark Applications & Cluster Status</strong>
        </div>
        <div className="d-flex align-items-center gap-3">
          {refreshing && (
            <div className="small text-light">
              <Spinner animation="border" size="sm" className="me-1" />
              Refreshing...
            </div>
          )}
          {lastUpdated && (
            <div className="small">
              {formatRelativeTime(lastUpdated)} • {formatRefreshPeriod(refreshInterval)}
            </div>
          )}
        </div>
      </Card.Header>
      <Card.Body>
        {loading && !sparkMasterStatus ? (
          <div className="text-center py-4">
            <span role="status" aria-live="polite" className="d-inline-flex align-items-center">
              <Spinner animation="border" variant="primary" aria-hidden="true" />
              <span className="visually-hidden ms-2">Loading…</span>
            </span>
            <div className="mt-2">Loading Spark cluster information...</div>
          </div>
        ) : sparkMasterStatus?.activeapps && sparkMasterStatus.activeapps.length > 0 ? (
          <div>
            <h6 className="mb-3 text-body-secondary">
              <FaTasks className="me-2" />
              Active Applications ({sparkMasterStatus.activeapps.length})
            </h6>
            <ThemedTable striped hover responsive className="mb-0">
              <thead className={isDark ? 'table-dark' : 'table-light'}>
                <tr>
                  <th><FaTasks className="me-1" /> App Name</th>
                  <th>App ID</th>
                  <th><FaUsers className="me-1" /> User</th>
                  <th>State</th>
                  <th><FaCog className="me-1" /> Cores</th>
                  <th><FaClock className="me-1" /> Submit Date</th>
                </tr>
              </thead>
              <tbody>
                {sparkMasterStatus.activeapps.map((app: SparkApplication, index: number) => (
                  <tr key={index}>
                    <td className="fw-semibold">{app.name}</td>
                    <td>
                      <code className="small text-body-secondary">{app.id}</code>
                    </td>
                    <td>{app.user}</td>
                    <td>
                      <Badge bg={getStateVariant(app.state)} className="px-2">
                        {app.state}
                      </Badge>
                    </td>
                    <td>{app.cores}</td>
                    <td className="text-body-secondary small">{formatDate(app.submitdate)}</td>
                  </tr>
                ))}
              </tbody>
            </ThemedTable>
          </div>
        ) : (
          <div className="text-center py-4 text-body-secondary">
            <FaTasks size={48} className="mb-3 opacity-50" />
            <div>No active applications found</div>
            <small>Applications will appear here when they are running</small>
          </div>
        )}
        
        {/* Enhanced Spark Cluster Status */}
        {sparkMasterStatus && (
          <div className="mt-4">
            <hr />
            <h6 className="mb-3 text-body-secondary">
              <FaServer className="me-2" />
              Cluster Overview
            </h6>
            
            <Row className="g-3">
              <Col md={6}>
                <Card className="border-0 bg-body-tertiary h-100">
                  <Card.Body className="p-3">
                    <div className="d-flex align-items-center mb-2">
                      <FaServer className="text-primary me-2" />
                      <strong>Master Status</strong>
                    </div>
                    <div className="small text-body-secondary mb-1">Master URL:</div>
                    <div className="fw-semibold mb-2">
                      <code className="small">{sparkMasterStatus.url}</code>
                    </div>
                    <div className="small text-body-secondary mb-1">Status:</div>
                    <Badge bg={sparkMasterStatus.status === 'ALIVE' ? 'success' : 'danger'}>
                      {sparkMasterStatus.status}
                    </Badge>
                  </Card.Body>
                </Card>
              </Col>
              
              <Col md={6}>
                <Card className="border-0 bg-body-tertiary h-100">
                  <Card.Body className="p-3">
                    <div className="d-flex align-items-center mb-2">
                      <FaUsers className="text-info me-2" />
                      <strong>Workers</strong>
                    </div>
                    <div className="h4 mb-0 text-info">
                      {sparkMasterStatus.aliveworkers}
                      <small className="text-body-secondary h6"> alive</small>
                    </div>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
            
            <Row className="g-3 mt-1">
              <Col md={6}>
                <Card className="border-0 bg-body-tertiary h-100">
                  <Card.Body className="p-3">
                    <div className="d-flex align-items-center mb-2">
                      <FaCog className="text-warning me-2" />
                      <strong>CPU Cores</strong>
                    </div>
                    <div className="mb-2">
                      <span className="h5 text-warning">{sparkMasterStatus.coresused}</span>
                      <span className="text-body-secondary"> / {sparkMasterStatus.cores} used</span>
                    </div>
                    <ProgressBar 
                      now={coreUtilization} 
                      variant={coreUtilization > 80 ? 'danger' : coreUtilization > 60 ? 'warning' : 'success'}
                      className="mb-1"
                      style={{ height: '8px' }}
                    />
                    <small className="text-body-secondary">{coreUtilization.toFixed(1)}% utilization</small>
                  </Card.Body>
                </Card>
              </Col>
              
              <Col md={6}>
                <Card className="border-0 bg-body-tertiary h-100">
                  <Card.Body className="p-3">
                    <div className="d-flex align-items-center mb-2">
                      <FaMemory className="text-success me-2" />
                      <strong>Memory</strong>
                    </div>
                    <div className="mb-2">
                      <span className="h5 text-success">{Math.round(sparkMasterStatus.memoryused / 1024)}MB</span>
                      <span className="text-body-secondary"> / {Math.round(sparkMasterStatus.memory / 1024)}MB used</span>
                    </div>
                    <ProgressBar 
                      now={memoryUtilization} 
                      variant={memoryUtilization > 80 ? 'danger' : memoryUtilization > 60 ? 'warning' : 'success'}
                      className="mb-1"
                      style={{ height: '8px' }}
                    />
                    <small className="text-body-secondary">{memoryUtilization.toFixed(1)}% utilization</small>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default SparkApplicationsCard;
