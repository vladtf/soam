import React, { useEffect, useState } from 'react';
import { Card, Button, Table, Badge, Tabs, Tab, Row, Col } from 'react-bootstrap';
import { flushErrorQueue } from '../errors';
import { useError } from '../context/ErrorContext';
import DataTroubleshootingTool from '../components/DataTroubleshootingTool';
import EnrichmentDiagnosticCard from '../components/sensor-data/EnrichmentDiagnosticCard';
import EnrichmentStatusCard from '../components/EnrichmentStatusCard';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import { fetchSparkMasterStatus, SparkMasterStatus, fetchErrors, ClientErrorRow } from '../api/backendRequests';

const TroubleshootingPage: React.FC = () => {
  const { setError } = useError();
  const [rows, setRows] = useState<ClientErrorRow[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [sparkMasterStatus, setSparkMasterStatus] = useState<SparkMasterStatus | null>(null);
  const [sparkLoading, setSparkLoading] = useState<boolean>(false);
  const [lastSparkUpdate, setLastSparkUpdate] = useState<Date | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      await flushErrorQueue();
      const data = await fetchErrors(200);
      setRows(data || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : (e as any));
    } finally {
      setLoading(false);
    }
  };

  const loadSparkStatus = async () => {
    setSparkLoading(true);
    try {
      const status = await fetchSparkMasterStatus();
      setSparkMasterStatus(status);
      setLastSparkUpdate(new Date());
    } catch (e) {
      console.warn('Failed to load Spark status:', e);
      // Don't setError here as this is a background operation
    } finally {
      setSparkLoading(false);
    }
  };

  useEffect(() => {
    load();
    loadSparkStatus();
    const errorInterval = setInterval(load, 20000);
    const sparkInterval = setInterval(loadSparkStatus, 15000);
    return () => {
      clearInterval(errorInterval);
      clearInterval(sparkInterval);
    };
  }, []);

  return (
    <div className="container py-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h3 className="m-0">Troubleshooting</h3>
          <small className="text-muted">Diagnose system errors and data transformation issues</small>
        </div>
      </div>

      <Tabs defaultActiveKey="data" className="mb-4">
        <Tab eventKey="data" title="🔧 Data Pipeline">
          {/* System-level diagnostics */}
          <div className="mb-4">
            <h5 className="mb-3">System Diagnostics</h5>
            <EnrichmentDiagnosticCard />
          </div>
          
          {/* Detailed troubleshooting tool */}
          <div className="mb-4">
            <h5 className="mb-3">Field-Level Troubleshooting</h5>
            <DataTroubleshootingTool />
          </div>
        </Tab>

        <Tab eventKey="system" title="⚡ System Status">
          <Row className="g-3">
            <Col md={6}>
              <div className="mb-4">
                <h5 className="mb-3">Enrichment Status</h5>
                <EnrichmentStatusCard minutes={10} autoRefresh={true} />
              </div>
            </Col>
            <Col md={6}>
              <div className="mb-4">
                <h5 className="mb-3">Data Sources</h5>
                <Card className="mb-3 shadow-sm border-body">
                  <Card.Header className="bg-body-tertiary">Modular Data Source System</Card.Header>
                  <Card.Body>
                    <p className="text-muted mb-3">
                      SOAM now uses a modular data source system. Manage all your data sources from the dedicated page.
                    </p>
                    <Button 
                      variant="primary" 
                      onClick={() => window.location.href = '/data-sources'}
                    >
                      📊 Manage Data Sources
                    </Button>
                  </Card.Body>
                </Card>
              </div>
            </Col>
          </Row>
          
          <Row className="g-3">
            <Col xs={12}>
              <div className="mb-4">
                <h5 className="mb-3">Spark Applications</h5>
                <SparkApplicationsCard 
                  sparkMasterStatus={sparkMasterStatus} 
                  sparkStreamsStatus={null}
                  loading={sparkLoading}
                  lastUpdated={lastSparkUpdate}
                  refreshInterval={15000}
                />
              </div>
            </Col>
          </Row>
        </Tab>

        <Tab eventKey="errors" title="🐛 Client Errors">
          <div className="d-flex align-items-center justify-content-between mb-3">
            <h5 className="m-0">Client Exceptions</h5>
            <div className="d-flex gap-2">
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={() => { flushErrorQueue(true).catch(() => {}); }}
              >
                Flush local queue
              </Button>
              <Button variant="primary" size="sm" onClick={load} disabled={loading}>
                {loading ? 'Loading…' : 'Refresh'}
              </Button>
            </div>
          </div>

          <Card className="shadow-sm">
            <Card.Header className="bg-body-tertiary">Recent Errors</Card.Header>
            <div className="table-responsive">
              <Table hover size="sm" className="mb-0">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>When</th>
                    <th>Severity</th>
                    <th>Component</th>
                    <th>Context</th>
                    <th>Message</th>
                    <th>URL</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.id}>
                      <td>{r.id}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{r.created_at ? new Date(r.created_at).toLocaleString() : '-'}</td>
                      <td>
                        <Badge bg={r.severity === 'fatal' || r.severity === 'error' ? 'danger' : (r.severity === 'warn' ? 'warning' : 'secondary')}>{r.severity || 'info'}</Badge>
                      </td>
                      <td>{r.component || '-'}</td>
                      <td>{r.context || '-'}</td>
                      <td style={{ maxWidth: 'min(26vw, 420px)', overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.message}>{r.message}</td>
                      <td style={{ maxWidth: 'min(15vw, 220px)', overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.url || ''}>{r.url || '-'}</td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="text-center text-body-secondary py-3">No client errors recorded</td>
                    </tr>
                  )}
                </tbody>
              </Table>
            </div>
          </Card>
        </Tab>
      </Tabs>
    </div>
  );
};

export default TroubleshootingPage;


