import React, { useState, useEffect } from 'react';
import { Card, Badge, Row, Col, Alert, Spinner } from 'react-bootstrap';
import { getSchemaConfig, getSystemConfig, SchemaConfig, SystemConfig } from '../../api/backendRequests';

interface SchemaConfigurationProps {
  className?: string;
}

const SchemaConfiguration: React.FC<SchemaConfigurationProps> = ({ className }) => {
  const [schemaConfig, setSchemaConfig] = useState<SchemaConfig | null>(null);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfiguration = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [schema, system] = await Promise.all([
        getSchemaConfig(),
        getSystemConfig()
      ]);
      
      setSchemaConfig(schema);
      setSystemConfig(system);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfiguration();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <Card.Header>
          <h6 className="mb-0">⚙️ Schema Configuration</h6>
        </Card.Header>
        <Card.Body className="text-center">
          <Spinner animation="border" size="sm" />
          <span className="ms-2">Loading configuration...</span>
        </Card.Body>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <Card.Header>
          <h6 className="mb-0">⚙️ Schema Configuration</h6>
        </Card.Header>
        <Card.Body>
          <Alert variant="warning" className="mb-0">
            <small>Unable to load configuration: {error}</small>
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  const isUnionSchema = true; // Always union schema now
  const schemaType = schemaConfig?.schema_type || 'unknown';

  return (
    <Card className={className}>
      <Card.Header>
        <h6 className="mb-0">⚙️ Schema Configuration</h6>
        <small className="text-muted">Current data storage format</small>
      </Card.Header>
      <Card.Body>
        <Row className="mb-3">
          <Col>
            <div className="d-flex align-items-center gap-2 mb-2">
              <strong>Active Schema:</strong>
              <Badge 
                bg={isUnionSchema ? 'success' : 'info'} 
                className="text-uppercase"
              >
                {schemaType}
              </Badge>
            </div>
            <div className="small text-muted">
              {schemaConfig?.message}
            </div>
          </Col>
        </Row>

        {isUnionSchema ? (
          <Alert variant="success" className="mb-3">
            <div className="small">
              <strong>🚀 Union Schema Active</strong>
              <ul className="mt-1 mb-0" style={{ fontSize: '0.8rem' }}>
                <li>Flexible data storage for any sensor type</li>
                <li>Raw data preserved as JSON strings</li>
                <li>Normalized values stored as typed data</li>
                <li>Schema evolution without breaking changes</li>
              </ul>
            </div>
          </Alert>
        ) : (
          <Alert variant="info" className="mb-3">
            <div className="small">
              <strong>📊 Legacy Schema Active</strong>
              <ul className="mt-1 mb-0" style={{ fontSize: '0.8rem' }}>
                <li>Fixed column structure</li>
                <li>Direct SQL queries</li>
                <li>Backward compatible</li>
              </ul>
            </div>
          </Alert>
        )}

        {systemConfig && (
          <Row className="small">
            <Col md={6}>
              <h6 className="small mb-1">Storage Paths:</h6>
              <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                <div>📁 Raw: bronze/</div>
                <div>🪙 Gold: gold/five_min_avg</div>
                <div>✨ Enriched: gold/enriched</div>
                <div>🚨 Alerts: gold/temperature_alerts</div>
              </div>
            </Col>
            <Col md={6}>
              <h6 className="small mb-1">Stream Status:</h6>
              <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                <div>
                  ✨ Enrichment: {' '}
                  <Badge bg={systemConfig.streaming.enrichment_active ? 'success' : 'secondary'} style={{ fontSize: '0.6rem' }}>
                    {systemConfig.streaming.enrichment_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div>
                  🌡️ Temperature: {' '}
                  <Badge bg={systemConfig.streaming.temperature_active ? 'success' : 'secondary'} style={{ fontSize: '0.6rem' }}>
                    {systemConfig.streaming.temperature_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div>
                  🚨 Alerts: {' '}
                  <Badge bg={systemConfig.streaming.alert_active ? 'success' : 'secondary'} style={{ fontSize: '0.6rem' }}>
                    {systemConfig.streaming.alert_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
            </Col>
          </Row>
        )}

        <hr />
        <div className="text-center">
          <small className="text-muted">
            The system automatically uses Union Schema for flexible, future-proof data storage.
          </small>
        </div>
      </Card.Body>
    </Card>
  );
};

export default SchemaConfiguration;
