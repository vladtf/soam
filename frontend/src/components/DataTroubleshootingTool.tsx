import React, { useState } from 'react';
import { Card, Form, Button, Alert, Accordion, Badge, Table, Spinner, Row, Col } from 'react-bootstrap';
import { getConfig } from '../config';

interface FieldDiagnosticResult {
  sensor_id: string;
  field_name: string;
  minutes_back: number;
  ingestion_id?: string;
  timestamp: string;
  status: string;
  error?: string;
  raw_data_analysis: any;
  normalization_analysis: any;
  enrichment_analysis: any;
  gold_analysis: any;
  recommendations: string[];
}

interface PipelineTraceResult {
  sensor_id: string;
  minutes_back: number;
  timestamp: string;
  status: string;
  error?: string;
  pipeline_stages: {
    [stage: string]: {
      status: string;
      record_count?: number;
      columns?: string[];
      sample_records?: any[];
      error?: string;
    };
  };
}

// Helper function for API calls
async function doFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  let resultRaw: unknown;
  try {
    resultRaw = await response.json();
  } catch {
    resultRaw = undefined;
  }

  if (!response.ok) {
    const result = resultRaw as any;
    const detailMsg = result?.detail ?? response.statusText;
    throw new Error(detailMsg);
  }

  return resultRaw as T;
}

const DataTroubleshootingTool: React.FC = () => {
  const [sensorId, setSensorId] = useState('');
  const [fieldName, setFieldName] = useState('temperature');
  const [minutesBack, setMinutesBack] = useState(30);
  const [ingestionId, setIngestionId] = useState('');
  const [loading, setLoading] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<FieldDiagnosticResult | null>(null);
  const [pipelineTrace, setPipelineTrace] = useState<PipelineTraceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'field' | 'pipeline'>('field');

  const handleFieldDiagnosis = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setDiagnosticResult(null);

    try {
      const { backendUrl } = getConfig();
      const result = await doFetch<FieldDiagnosticResult>(`${backendUrl}/api/v1/troubleshooting/diagnose-field`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sensor_id: sensorId,
          field_name: fieldName,
          minutes_back: minutesBack,
          ingestion_id: ingestionId || undefined
        })
      });

      setDiagnosticResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to diagnose field');
    } finally {
      setLoading(false);
    }
  };

  const handlePipelineTrace = async () => {
    setLoading(true);
    setError(null);
    setPipelineTrace(null);

    try {
      const { backendUrl } = getConfig();
      const result = await doFetch<PipelineTraceResult>(`${backendUrl}/api/v1/troubleshooting/trace-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sensor_id: sensorId,
          minutes_back: minutesBack
        })
      });

      setPipelineTrace(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trace pipeline');
    } finally {
      setLoading(false);
    }
  };

  const getStatusVariant = (status: string): string => {
    switch (status) {
      case 'found':
      case 'success':
      case 'healthy':
        return 'success';
      case 'no_data':
        return 'warning';
      case 'error':
      case 'unhealthy':
        return 'danger';
      default:
        return 'secondary';
    }
  };

  const formatRecommendation = (rec: string): { icon: string; text: string; variant: string } => {
    if (rec.startsWith('✅')) {
      return { icon: '✅', text: rec.substring(2), variant: 'success' };
    } else if (rec.startsWith('❌')) {
      return { icon: '❌', text: rec.substring(2), variant: 'danger' };
    } else if (rec.startsWith('⚠️')) {
      return { icon: '⚠️', text: rec.substring(2), variant: 'warning' };
    } else if (rec.startsWith('ℹ️')) {
      return { icon: 'ℹ️', text: rec.substring(2), variant: 'info' };
    }
    return { icon: '', text: rec, variant: 'secondary' };
  };

  const renderFieldVariants = (variants: string[]) => (
    <div className="d-flex flex-wrap gap-1">
      {variants.map((variant, idx) => (
        <Badge key={idx} bg="secondary" className="me-1">
          {variant}
        </Badge>
      ))}
    </div>
  );

  const renderSampleValues = (samples: any[]) => (
    <Table size="sm" striped>
      <thead>
        <tr>
          <th>Field</th>
          <th>Value</th>
          <th>Type</th>
          <th>Timestamp</th>
        </tr>
      </thead>
      <tbody>
        {samples.slice(0, 5).map((sample, idx) => (
          <tr key={idx}>
            <td><code>{sample.field_variant || sample.field}</code></td>
            <td>{JSON.stringify(sample.value)}</td>
            <td><Badge bg="info">{sample.type}</Badge></td>
            <td>{new Date(sample.timestamp).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderNormalizationValues = (values: any[]) => (
    <Table size="sm" striped>
      <thead>
        <tr>
          <th>Raw Field</th>
          <th>Canonical Field</th>
          <th>Before</th>
          <th>After</th>
          <th>Match</th>
        </tr>
      </thead>
      <tbody>
        {values.map((val, idx) => (
          <tr key={idx}>
            <td><code>{val.raw_field}</code></td>
            <td><code>{val.canonical_field}</code></td>
            <td>{JSON.stringify(val.before_values)}</td>
            <td>{JSON.stringify(val.after_values)}</td>
            <td>
              {val.values_match.every((m: boolean) => m) ? 
                <Badge bg="success">✓</Badge> : 
                <Badge bg="danger">✗</Badge>
              }
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderPipelineStage = (stageName: string, stage: any) => {
    const cleanStageName = stageName.replace(/^\d+_/, '').replace(/_/g, ' ').toUpperCase();
    
    return (
      <Card className="mb-3">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <h6 className="mb-0">{cleanStageName}</h6>
          <Badge bg={getStatusVariant(stage.status)}>
            {stage.status}
          </Badge>
        </Card.Header>
        <Card.Body>
          {stage.status === 'found' && (
            <>
              <p><strong>Records:</strong> {stage.record_count}</p>
              <p><strong>Columns:</strong> {stage.columns?.length || 0}</p>
              
              {stage.columns && stage.columns.length > 0 && (
                <div className="mb-3">
                  <strong>Column Names:</strong>
                  <div className="d-flex flex-wrap gap-1 mt-1">
                    {stage.columns.map((col: string, idx: number) => (
                      <Badge key={idx} bg="outline-secondary" text="dark" className="me-1">
                        {col}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {stage.sample_records && stage.sample_records.length > 0 && (
                <Accordion className="mt-3">
                  <Accordion.Item eventKey="0">
                    <Accordion.Header>Sample Records ({stage.sample_records.length})</Accordion.Header>
                    <Accordion.Body>
                      <pre className="small bg-light p-2 rounded">
                        {JSON.stringify(stage.sample_records, null, 2)}
                      </pre>
                    </Accordion.Body>
                  </Accordion.Item>
                </Accordion>
              )}
            </>
          )}
          
          {stage.status === 'no_data' && (
            <Alert variant="warning" className="mb-0">
              No data found for this stage
            </Alert>
          )}
          
          {stage.status === 'error' && (
            <Alert variant="danger" className="mb-0">
              Error: {stage.error}
            </Alert>
          )}
        </Card.Body>
      </Card>
    );
  };

  return (
    <div className="troubleshooting-tool">
      <Card>
        <Card.Header>
          <h5 className="mb-0">🔧 Data Troubleshooting Tool</h5>
          <small className="text-muted">
            Diagnose data transformation issues across the pipeline
          </small>
        </Card.Header>
        <Card.Body>
          {/* Configuration Form */}
          <Form onSubmit={handleFieldDiagnosis} className="mb-4">
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Sensor ID</Form.Label>
                  <Form.Control
                    type="text"
                    value={sensorId}
                    onChange={(e) => setSensorId(e.target.value)}
                    placeholder="e.g., sensor_001"
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Field Name</Form.Label>
                  <Form.Control
                    type="text"
                    value={fieldName}
                    onChange={(e) => setFieldName(e.target.value)}
                    placeholder="e.g., temperature"
                    required
                  />
                </Form.Group>
              </Col>
            </Row>
            
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Minutes Back</Form.Label>
                  <Form.Control
                    type="number"
                    value={minutesBack}
                    onChange={(e) => setMinutesBack(parseInt(e.target.value))}
                    min={1}
                    max={1440}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Ingestion ID (Optional)</Form.Label>
                  <Form.Control
                    type="text"
                    value={ingestionId}
                    onChange={(e) => setIngestionId(e.target.value)}
                    placeholder="Filter by specific ingestion ID"
                  />
                </Form.Group>
              </Col>
            </Row>

            <div className="d-flex gap-2">
              <Button
                type="submit"
                variant="primary"
                disabled={loading || !sensorId}
              >
                {loading ? <Spinner size="sm" /> : <span aria-hidden="true">🔍</span>}
                <span className="visually-hidden">Diagnose Field</span>
                {!loading && ' Diagnose Field'}
              </Button>
              
              <Button
                type="button"
                variant="outline-primary"
                disabled={loading || !sensorId}
                onClick={handlePipelineTrace}
              >
                {loading ? <Spinner size="sm" /> : <span aria-hidden="true">🔄</span>}
                <span className="visually-hidden">Trace Pipeline</span>
                {!loading && ' Trace Pipeline'}
              </Button>
            </div>
          </Form>

          {/* Error Display */}
          {error && (
            <Alert variant="danger" className="mb-4">
              <strong>Error:</strong> {error}
            </Alert>
          )}

          {/* Results Tabs */}
          <div className="mb-3">
            <Button
              variant={activeTab === 'field' ? 'primary' : 'outline-primary'}
              className="me-2"
              onClick={() => setActiveTab('field')}
              disabled={!diagnosticResult}
            >
              Field Diagnosis
            </Button>
            <Button
              variant={activeTab === 'pipeline' ? 'primary' : 'outline-primary'}
              onClick={() => setActiveTab('pipeline')}
              disabled={!pipelineTrace}
            >
              Pipeline Trace
            </Button>
          </div>

          {/* Field Diagnosis Results */}
          {activeTab === 'field' && diagnosticResult && (
            <div>
              {/* Recommendations */}
              {diagnosticResult.recommendations && diagnosticResult.recommendations.length > 0 && (
                <Card className="mb-4">
                  <Card.Header>
                    <h6 className="mb-0">📋 Recommendations</h6>
                  </Card.Header>
                  <Card.Body>
                    {diagnosticResult.recommendations.map((rec, idx) => {
                      const formatted = formatRecommendation(rec);
                      return (
                        <Alert key={idx} variant={formatted.variant} className="mb-2">
                          {formatted.icon && <span className="me-2">{formatted.icon}</span>}
                          {formatted.text}
                        </Alert>
                      );
                    })}
                  </Card.Body>
                </Card>
              )}

              {/* Detailed Analysis */}
              <Accordion>
                {/* Raw Data Analysis */}
                <Accordion.Item eventKey="0">
                  <Accordion.Header>
                    🗂️ Raw Data Analysis
                    <Badge bg={diagnosticResult.raw_data_analysis.found_data ? 'success' : 'warning'} className="ms-2">
                      {diagnosticResult.raw_data_analysis.found_data ? 'Data Found' : 'No Data'}
                    </Badge>
                  </Accordion.Header>
                  <Accordion.Body>
                    {diagnosticResult.raw_data_analysis.found_data ? (
                      <>
                        <p><strong>Records:</strong> {diagnosticResult.raw_data_analysis.record_count}</p>
                        <p><strong>Field Variants Found:</strong></p>
                        {renderFieldVariants(diagnosticResult.raw_data_analysis.field_variants_found || [])}
                        
                        {diagnosticResult.raw_data_analysis.field_values_sample && (
                          <div className="mt-3">
                            <strong>Sample Values:</strong>
                            {renderSampleValues(diagnosticResult.raw_data_analysis.field_values_sample)}
                          </div>
                        )}
                      </>
                    ) : (
                      <Alert variant="warning">No raw data found for this sensor and time range.</Alert>
                    )}
                  </Accordion.Body>
                </Accordion.Item>

                {/* Normalization Analysis */}
                <Accordion.Item eventKey="1">
                  <Accordion.Header>
                    ⚙️ Normalization Analysis
                    <Badge bg={diagnosticResult.normalization_analysis.transformation_applied ? 'success' : 'secondary'} className="ms-2">
                      {diagnosticResult.normalization_analysis.transformation_applied ? 'Rules Applied' : 'No Rules'}
                    </Badge>
                  </Accordion.Header>
                  <Accordion.Body>
                    {Object.keys(diagnosticResult.normalization_analysis.field_mapping || {}).length > 0 ? (
                      <>
                        <strong>Field Mappings:</strong>
                        <Table size="sm" className="mt-2">
                          <thead>
                            <tr>
                              <th>Raw Field</th>
                              <th>Canonical Field</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(diagnosticResult.normalization_analysis.field_mapping).map(([raw, canonical], idx) => (
                              <tr key={idx}>
                                <td><code>{raw}</code></td>
                                <td><code>{canonical as string}</code></td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>

                        {diagnosticResult.normalization_analysis.normalized_values && (
                          <div className="mt-3">
                            <strong>Normalization Results:</strong>
                            {renderNormalizationValues(diagnosticResult.normalization_analysis.normalized_values)}
                          </div>
                        )}
                      </>
                    ) : (
                      <Alert variant="info">No normalization rules applied to this field.</Alert>
                    )}
                  </Accordion.Body>
                </Accordion.Item>

                {/* Enrichment Analysis */}
                <Accordion.Item eventKey="2">
                  <Accordion.Header>
                    🔗 Enrichment Analysis
                    <Badge bg={diagnosticResult.enrichment_analysis.found_in_enriched ? 'success' : 'warning'} className="ms-2">
                      {diagnosticResult.enrichment_analysis.found_in_enriched ? 'Found' : 'Missing'}
                    </Badge>
                  </Accordion.Header>
                  <Accordion.Body>
                    <p><strong>Records in Enriched Layer:</strong> {diagnosticResult.enrichment_analysis.record_count}</p>
                    
                    <Row>
                      <Col md={6}>
                        <p><strong>Field in Sensor Data:</strong> {' '}
                          <Badge bg={diagnosticResult.enrichment_analysis.field_in_sensor_data ? 'success' : 'danger'}>
                            {diagnosticResult.enrichment_analysis.field_in_sensor_data ? 'Yes' : 'No'}
                          </Badge>
                        </p>
                      </Col>
                      <Col md={6}>
                        <p><strong>Field in Normalized Data:</strong> {' '}
                          <Badge bg={diagnosticResult.enrichment_analysis.field_in_normalized_data ? 'success' : 'danger'}>
                            {diagnosticResult.enrichment_analysis.field_in_normalized_data ? 'Yes' : 'No'}
                          </Badge>
                        </p>
                      </Col>
                    </Row>

                    {diagnosticResult.enrichment_analysis.union_schema_analysis?.field_values_found && (
                      <div className="mt-3">
                        <strong>Field Values Found:</strong>
                        {renderSampleValues(diagnosticResult.enrichment_analysis.union_schema_analysis.field_values_found)}
                      </div>
                    )}
                  </Accordion.Body>
                </Accordion.Item>

                {/* Gold Analysis */}
                <Accordion.Item eventKey="3">
                  <Accordion.Header>
                    🥈 Gold Layer Analysis
                    <Badge bg={diagnosticResult.gold_analysis.found_in_gold ? 'success' : 'warning'} className="ms-2">
                      {diagnosticResult.gold_analysis.found_in_gold ? 'Found' : 'Missing'}
                    </Badge>
                  </Accordion.Header>
                  <Accordion.Body>
                    {diagnosticResult.gold_analysis.found_in_gold ? (
                      <>
                        <p><strong>Records:</strong> {diagnosticResult.gold_analysis.record_count}</p>

                        {Object.keys(diagnosticResult.gold_analysis.field_aggregations || {}).length > 0 && (
                          <div className="mt-3">
                            <strong>Field Statistics:</strong>
                            <Table size="sm" className="mt-2">
                              <thead>
                                <tr>
                                  <th>Field</th>
                                  <th>Count</th>
                                  <th>Min</th>
                                  <th>Max</th>
                                  <th>Avg</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(diagnosticResult.gold_analysis.field_aggregations).map(([field, stats], idx) => (
                                  <tr key={idx}>
                                    <td><code>{field}</code></td>
                                    <td>{(stats as any).count}</td>
                                    <td>{(stats as any).min_value}</td>
                                    <td>{(stats as any).max_value}</td>
                                    <td>{(stats as any).avg_value}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </Table>
                          </div>
                        )}
                      </>
                    ) : (
                      <Alert variant="info">No aggregated data found in gold layer.</Alert>
                    )}
                  </Accordion.Body>
                </Accordion.Item>
              </Accordion>
            </div>
          )}

          {/* Pipeline Trace Results */}
          {activeTab === 'pipeline' && pipelineTrace && (
            <div>
              <Alert variant="info" className="mb-4">
                <strong>Pipeline Trace for Sensor:</strong> {pipelineTrace.sensor_id} <br />
                <strong>Time Range:</strong> Last {pipelineTrace.minutes_back} minutes
              </Alert>

              {Object.entries(pipelineTrace.pipeline_stages)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([stageName, stage]) => renderPipelineStage(stageName, stage))
              }
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default DataTroubleshootingTool;
