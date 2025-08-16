import React, { useState } from 'react';
import { Card, Button, Alert, Badge, Row, Col, ListGroup, Spinner } from 'react-bootstrap';
import { fetchEnrichmentDiagnostic, EnrichmentDiagnosticData, fetchIngestorTopicAnalysis, IngestorTopicAnalysis } from '../../api/backendRequests';

const EnrichmentDiagnosticCard: React.FC = () => {
  const [diagnostic, setDiagnostic] = useState<EnrichmentDiagnosticData | null>(null);
  const [ingestorAnalysis, setIngestorAnalysis] = useState<IngestorTopicAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [ingestorLoading, setIngestorLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDiagnostic, setShowDiagnostic] = useState(false);

  const runDiagnostic = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchEnrichmentDiagnostic();
      setDiagnostic(result);
      setShowDiagnostic(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run diagnostic');
    } finally {
      setLoading(false);
    }
  };

  const runIngestorAnalysis = async () => {
    setIngestorLoading(true);
    setError(null);
    try {
      const result = await fetchIngestorTopicAnalysis();
      console.log('Ingestor analysis result:', result);
      setIngestorAnalysis(result);
    } catch (err) {
      console.error('Ingestor analysis error:', err);
      setError(err instanceof Error ? err.message : 'Failed to run ingestor analysis');
    } finally {
      setIngestorLoading(false);
    }
  };

  return (
    <Card className="mb-3">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <h5 className="mb-0">🔍 Enrichment Filtering Diagnostic</h5>
        <div>
          <Button
            variant="outline-info"
            size="sm"
            onClick={runIngestorAnalysis}
            disabled={ingestorLoading}
            className="me-2"
          >
            {ingestorLoading ? (
              <>
                <Spinner animation="border" size="sm" className="me-2" />
                Analyzing...
              </>
            ) : (
              'Analyze Topics'
            )}
          </Button>
          <Button
            variant="outline-primary"
            size="sm"
            onClick={runDiagnostic}
            disabled={loading}
          >
            {loading ? (
              <>
                <Spinner animation="border" size="sm" className="me-2" />
                Running...
              </>
            ) : (
              'Run Diagnostic'
            )}
          </Button>
        </div>
      </Card.Header>
      
      {error && (
        <Card.Body>
          <Alert variant="danger">
            <strong>Error:</strong> {error}
          </Alert>
        </Card.Body>
      )}

      {/* Ingestor Analysis Results */}
      {ingestorAnalysis && (
        <Card.Body>
          <h6>📡 Ingestor Topic Analysis</h6>
          <p className="text-muted mb-3">
            Analysis of MQTT topics and sensor IDs received by the ingestor
          </p>
          
          {/* Debug Info */}
          <Alert variant="secondary" className="mb-3">
            <small>
              <strong>Debug:</strong> Analysis object exists: {ingestorAnalysis ? 'Yes' : 'No'}, 
              Partitions keys: {ingestorAnalysis ? Object.keys(ingestorAnalysis.partitions).join(', ') : 'None'}, 
              Length: {ingestorAnalysis ? Object.keys(ingestorAnalysis.partitions).length : 0}
            </small>
          </Alert>
          
          {/* Buffer Status */}
          <Alert variant="info" className="mb-3">
            <Row>
              <Col md={6}>
                <strong>Connection Status:</strong>
                <br />
                <small>
                  MQTT Handler: {ingestorAnalysis.buffer_status.mqtt_handler_active ? '✅ Active' : '❌ Inactive'}
                  <br />
                  {ingestorAnalysis.buffer_status.active_broker && (
                    <>Broker: {ingestorAnalysis.buffer_status.active_broker}<br /></>
                  )}
                  {ingestorAnalysis.buffer_status.subscribed_topic && (
                    <>Topic: {ingestorAnalysis.buffer_status.subscribed_topic}</>
                  )}
                </small>
              </Col>
              <Col md={6}>
                <strong>Buffer Status:</strong>
                <br />
                <small>
                  Messages in buffers: {ingestorAnalysis.buffer_status.total_messages_in_buffers}
                  <br />
                  Max per partition: {ingestorAnalysis.buffer_status.max_rows_per_partition}
                  <br />
                  Active partitions: {Object.keys(ingestorAnalysis.partitions).length}
                </small>
              </Col>
            </Row>
          </Alert>
          
          {Object.keys(ingestorAnalysis.partitions).length === 0 ? (
            <Alert variant="warning">
              <strong>No partitions found.</strong>
              <br />
              This could mean:
              <ul className="mb-0 mt-2">
                <li>No messages have been received yet</li>
                <li>MQTT client is not connected ({ingestorAnalysis.buffer_status.mqtt_handler_active ? 'Handler is active' : 'Handler is inactive'})</li>
                <li>Simulators are not running or not publishing data</li>
              </ul>
            </Alert>
          ) : (
            <>
              <h6>Found {Object.keys(ingestorAnalysis.partitions).length} partitions!</h6>
              <Row>
                <Col md={12}>
                  <h6>Partitions (Ingestion IDs)</h6>
                  <ListGroup className="mb-3">
                    {Object.entries(ingestorAnalysis.partitions).map(([ingestionId, data]) => (
                      <ListGroup.Item key={ingestionId} className="d-flex justify-content-between align-items-center">
                        <div>
                          <code className="small">{ingestionId}</code>
                          <br />
                          <small className="text-muted">
                            Topics: {data.topics_seen.join(', ') || 'None'}
                            <br />
                            Sensors: {data.sensor_ids_seen.slice(0, 3).join(', ')}
                            {data.sensor_ids_seen.length > 3 && ` +${data.sensor_ids_seen.length - 3} more`}
                            {data.status && <><br />Status: {data.status}</>}
                          </small>
                        </div>
                        <div>
                          <Badge bg={data.message_count > 0 ? "secondary" : "light"}>
                            {data.message_count} msgs
                          </Badge>
                        </div>
                      </ListGroup.Item>
                    ))}
                  </ListGroup>
                </Col>
              </Row>
              
              <Row>
                <Col md={12}>
                  <h6>Topic → Ingestion ID Mapping</h6>
                  {Object.keys(ingestorAnalysis.topic_to_ingestion_id_mapping).length === 0 ? (
                    <Alert variant="info">No topic mappings found in current buffer.</Alert>
                  ) : (
                    <ListGroup className="mb-3">
                      {Object.entries(ingestorAnalysis.topic_to_ingestion_id_mapping).map(([topic, ingestionIds]) => (
                        <ListGroup.Item key={topic} className="d-flex justify-content-between align-items-center">
                          <div>
                            <code className="small">{topic}</code>
                            <br />
                            <small className="text-muted">
                              Ingestion IDs: {ingestionIds.join(', ')}
                            </small>
                          </div>
                          <Badge bg="info">{ingestionIds.length} partition{ingestionIds.length !== 1 ? 's' : ''}</Badge>
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  )}
                </Col>
              </Row>
            </>
          )}
          
          <Alert variant="success" className="mt-3">
            <strong>Analysis Complete:</strong> {ingestorAnalysis.buffer_status.total_messages_in_buffers} messages in {ingestorAnalysis.total_partitions} partitions
            {ingestorAnalysis.buffer_status.total_messages_in_buffers === 0 && (
              <span className="text-muted"> (buffers are empty - data may have been flushed to MinIO or no recent activity)</span>
            )}
          </Alert>
        </Card.Body>
      )}

      {showDiagnostic && diagnostic && (
        <Card.Body>
          <h6>🔍 Backend Enrichment Analysis</h6>
          <Row>
            <Col md={6}>
              <h6>Registered Devices ({diagnostic.registered_devices.length})</h6>
              <ListGroup className="mb-3">
                {diagnostic.registered_devices.map((device) => (
                  <ListGroup.Item key={device.id} className="d-flex justify-content-between align-items-center">
                    <div>
                      <strong>{device.name || `Device ${device.id}`}</strong>
                      <br />
                      <small className="text-muted">
                        Ingestion ID: {device.ingestion_id || 'None (Wildcard)'}
                      </small>
                    </div>
                    <div>
                      {device.enabled ? (
                        <Badge bg="success">Enabled</Badge>
                      ) : (
                        <Badge bg="secondary">Disabled</Badge>
                      )}
                      {device.is_wildcard && (
                        <Badge bg="warning" className="ms-1">Wildcard</Badge>
                      )}
                    </div>
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Col>
            
            <Col md={6}>
              <h6>Enriched Data Analysis</h6>
              <div className="mb-3">
                <p>
                  <strong>Total Sensors in Enriched Data:</strong> {diagnostic.total_enriched_sensors}
                </p>
                <p>
                  <strong>Ingestion IDs Found:</strong> {diagnostic.enriched_data_ingestion_ids.length}
                </p>
              </div>
              
              <h6>Sensors by Ingestion ID</h6>
              <ListGroup className="mb-3">
                {Object.entries(diagnostic.enriched_sensors_by_ingestion_id).map(([ingestionId, sensors]) => (
                  <ListGroup.Item key={ingestionId}>
                    <div className="d-flex justify-content-between align-items-center">
                      <div>
                        <strong>{ingestionId}</strong>
                        <br />
                        <small className="text-muted">
                          {sensors.slice(0, 3).join(', ')}
                          {sensors.length > 3 && ` +${sensors.length - 3} more`}
                        </small>
                      </div>
                      <Badge bg="info">{sensors.length} sensors</Badge>
                    </div>
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Col>
          </Row>

          {diagnostic.potential_issues.length > 0 && (
            <div className="mt-3">
              <h6>⚠️ Potential Issues</h6>
              {diagnostic.potential_issues.map((issue, index) => (
                <Alert 
                  key={index} 
                  variant={issue.includes('WARNING') ? 'warning' : 'info'}
                  className="mb-2"
                >
                  {issue}
                </Alert>
              ))}
            </div>
          )}

          {diagnostic.potential_issues.length === 0 && (
            <Alert variant="success" className="mt-3">
              ✅ No obvious issues detected with enrichment filtering.
            </Alert>
          )}
        </Card.Body>
      )}

      {!showDiagnostic && !ingestorAnalysis && !error && (
        <Card.Body>
          <p className="text-muted mb-0">
            <strong>Analyze Topics:</strong> View what MQTT topics and sensor IDs are being received by the ingestor.
            <br />
            <strong>Run Diagnostic:</strong> Analyze why certain sensors are being processed in the enrichment pipeline.
          </p>
        </Card.Body>
      )}
    </Card>
  );
};

export default EnrichmentDiagnosticCard;
