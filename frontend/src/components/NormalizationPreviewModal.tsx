import React, { useState, useEffect } from 'react';
import { 
  Row, Col, Card, Table, Button, Alert, Spinner, Form, 
  Modal, Badge, Tabs, Tab} from 'react-bootstrap';
import { 
  FaEye, FaPlay, FaPlus, FaTrash, FaCheck, FaTimes, 
  FaExclamationTriangle, FaInfoCircle, FaSave 
} from 'react-icons/fa';
import { 
  getNormalizationSampleData, 
  previewNormalization, 
  validateNormalizationRules,
  createMultipleNormalizationRules,
  NormalizationPreviewSampleData,
  NormalizationPreviewResult 
} from '../api/backendRequests';

interface NormalizationRule {
  raw_key: string;
  canonical_key: string;
  ingestion_id?: string;
}

const NormalizationPreviewModal: React.FC<{
  show: boolean;
  onHide: () => void;
}> = ({ show, onHide }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('preview');
  
  // Sample data state
  const [sampleData, setSampleData] = useState<NormalizationPreviewSampleData | null>(null);
  const [selectedIngestionId, setSelectedIngestionId] = useState<string>('');
  const [sampleLimit, setSampleLimit] = useState<number>(100);
  
  // Preview state
  const [previewResult, setPreviewResult] = useState<NormalizationPreviewResult | null>(null);
  const [customRules, setCustomRules] = useState<NormalizationRule[]>([]);
  
  // Validation state
  const [validationResult, setValidationResult] = useState<any>(null);
  
  // Save state
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string>('');

  useEffect(() => {
    if (show) {
      loadSampleData();
    } else {
      // Reset messages when modal is closed
      setSaveSuccess('');
      setError('');
    }
  }, [show]);

  const loadSampleData = async () => {
    setLoading(true);
    setError('');
    
    try {
      console.log('Loading sample data with params:', { 
        ingestionId: selectedIngestionId, 
        limit: sampleLimit 
      });
      
      const result = await getNormalizationSampleData(selectedIngestionId || undefined, sampleLimit);
      
      console.log('Sample data loaded:', result);
      setSampleData(result);
    } catch (err) {
      console.error('Error loading sample data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load sample data');
    } finally {
      setLoading(false);
    }
  };

  const runPreview = async () => {
    if (!sampleData) {
      setError('No sample data available');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const result = await previewNormalization({
        ingestion_id: selectedIngestionId || undefined,
        custom_rules: customRules.length > 0 ? customRules : undefined,
        sample_limit: sampleLimit
      });
      
      setPreviewResult(result.preview);
      setActiveTab('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run preview');
    } finally {
      setLoading(false);
    }
  };

  const validateRules = async () => {
    if (customRules.length === 0) {
      setError('No custom rules to validate');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const result = await validateNormalizationRules({
        rules: customRules,
        ingestion_id: selectedIngestionId || undefined,
        sample_limit: sampleLimit
      });
      
      setValidationResult(result.validation);
      setActiveTab('validation');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate rules');
    } finally {
      setLoading(false);
    }
  };

  const saveNormalizationRules = async () => {
    if (customRules.length === 0) {
      setError('No rules to save');
      return;
    }
    
    setSaving(true);
    setError('');
    setSaveSuccess('');
    
    try {
      // Convert custom rules to the format expected by the API
      const rulesToSave = customRules
        .filter(rule => rule.raw_key.trim() && rule.canonical_key.trim())
        .map(rule => ({
          raw_key: rule.raw_key.trim(),
          canonical_key: rule.canonical_key.trim(),
          ingestion_id: rule.ingestion_id || selectedIngestionId || undefined,
          created_by: 'user' // TODO: Get actual username from context/auth
        }));
      
      if (rulesToSave.length === 0) {
        setError('No valid rules to save. Please ensure all rules have both raw key and canonical key filled.');
        return;
      }
      
      await createMultipleNormalizationRules(rulesToSave);
      setSaveSuccess(`Successfully saved ${rulesToSave.length} normalization rule${rulesToSave.length > 1 ? 's' : ''}`);
      
      // Clear custom rules after successful save
      setCustomRules([]);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save normalization rules');
    } finally {
      setSaving(false);
    }
  };

  const saveAppliedRulesAsNormalizationRules = async () => {
    if (!previewResult || !previewResult.applied_rules || previewResult.applied_rules.length === 0) {
      setError('No applied rules to save');
      return;
    }
    
    setSaving(true);
    setError('');
    setSaveSuccess('');
    
    try {
      // Convert applied rules to normalization rules (only save the ones that are 'custom' type)
      const rulesToSave = previewResult.applied_rules
        .filter(rule => rule.type === 'custom') // Only save custom rules, not existing ones
        .map(rule => ({
          raw_key: rule.raw_key,
          canonical_key: rule.canonical_key,
          ingestion_id: selectedIngestionId || undefined,
          created_by: 'user' // TODO: Get actual username from context/auth
        }));
      
      if (rulesToSave.length === 0) {
        setError('No new custom rules to save from the preview results');
        return;
      }
      
      await createMultipleNormalizationRules(rulesToSave);
      setSaveSuccess(`Successfully saved ${rulesToSave.length} normalization rule${rulesToSave.length > 1 ? 's' : ''} from preview results`);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save applied rules as normalization rules');
    } finally {
      setSaving(false);
    }
  };

  const addRulesFromUnmappedColumns = () => {
    if (!previewResult || !previewResult.unmapped_columns || previewResult.unmapped_columns.length === 0) {
      setError('No unmapped columns to create rules from');
      return;
    }
    
    // Create new rules from unmapped columns
    const newRules = previewResult.unmapped_columns.map(column => ({
      raw_key: column,
      canonical_key: '', // User will need to fill this
      ingestion_id: selectedIngestionId || ''
    }));
    
    // Add to existing custom rules
    setCustomRules([...customRules, ...newRules]);
    
    // Switch to the custom rules tab
    setActiveTab('rules');
  };

  const addCustomRule = () => {
    setCustomRules([...customRules, { raw_key: '', canonical_key: '', ingestion_id: selectedIngestionId }]);
  };

  const removeCustomRule = (index: number) => {
    setCustomRules(customRules.filter((_, i) => i !== index));
  };

  const updateCustomRule = (index: number, field: keyof NormalizationRule, value: string) => {
    const updated = [...customRules];
    updated[index] = { ...updated[index], [field]: value };
    setCustomRules(updated);
  };

  const renderSampleDataTable = () => {
    if (!sampleData || !sampleData.data || sampleData.data.length === 0) {
      return (
        <Alert variant="info">
          <FaInfoCircle className="me-2" />
          No sample data available. Try selecting a different ingestion ID or check if data exists.
        </Alert>
      );
    }

    const displayData = sampleData.data.slice(0, 10); // Show first 10 rows
    const columns = (sampleData.columns || []).filter(col => !col.startsWith('_')); // Hide internal columns

    return (
      <div>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <small className="text-muted">
            Showing {displayData.length} of {sampleData.total_records} records, {columns.length} columns
          </small>
          <Button variant="outline-primary" size="sm" onClick={loadSampleData} disabled={loading}>
            {loading ? <Spinner size="sm" /> : 'Refresh'}
          </Button>
        </div>
        
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          <Table striped bordered hover size="sm" className="mb-0">
            <thead className="sticky-top bg-light">
              <tr>
                {columns.map(col => (
                  <th key={col} style={{ whiteSpace: 'nowrap' }}>
                    <small>{col}</small>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayData.map((row, index) => (
                <tr key={index}>
                  {columns.map(col => (
                    <td key={col} style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <small>{String(row[col] || '').slice(0, 50)}</small>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>
    );
  };

  const renderPreviewResults = () => {
    if (!previewResult) {
      return (
        <Alert variant="info">
          <FaInfoCircle className="me-2" />
          Click "Run Preview" to see how normalization rules will transform your data.
        </Alert>
      );
    }

    const originalData = previewResult.original_data || [];
    const normalizedData = previewResult.normalized_data || [];
    const appliedRules = previewResult.applied_rules || [];
    const unmappedColumns = previewResult.unmapped_columns || [];

    return (
      <div>
        {/* Summary Cards */}
        <Row className="mb-3">
          <Col md={3}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-primary">{previewResult.summary?.total_records || 0}</h5>
                <small>Records</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-success">{previewResult.summary?.rules_applied || 0}</h5>
                <small>Rules Applied</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-info">{previewResult.summary?.columns_mapped || 0}</h5>
                <small>Columns Mapped</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-warning">{previewResult.summary?.unmapped_columns || 0}</h5>
                <small>Unmapped</small>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        {/* Before/After Comparison */}
        <Row>
          <Col md={6}>
            <Card>
              <Card.Header>
                <FaTimes className="text-muted me-2" />
                Original Data
              </Card.Header>
              <Card.Body style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {originalData.length > 0 ? (
                  <Table striped size="sm">
                    <thead>
                      <tr>
                        {Object.keys(originalData[0]).map(col => (
                          <th key={col}><small>{col}</small></th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {originalData.slice(0, 5).map((row, index) => (
                        <tr key={index}>
                          {Object.values(row).map((val, i) => (
                            <td key={i}><small>{String(val || '').slice(0, 30)}</small></td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <p className="text-muted">No data to display</p>
                )}
              </Card.Body>
            </Card>
          </Col>
          <Col md={6}>
            <Card>
              <Card.Header>
                <FaCheck className="text-success me-2" />
                Normalized Data
              </Card.Header>
              <Card.Body style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {normalizedData.length > 0 ? (
                  <Table striped size="sm">
                    <thead>
                      <tr>
                        {Object.keys(normalizedData[0]).map(col => (
                          <th key={col}><small>{col}</small></th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {normalizedData.slice(0, 5).map((row, index) => (
                        <tr key={index}>
                          {Object.values(row).map((val, i) => (
                            <td key={i}><small>{String(val || '').slice(0, 30)}</small></td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <p className="text-muted">No data to display</p>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>

        {/* Applied Rules */}
        {appliedRules.length > 0 && (
          <Card className="mt-3">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Applied Rules</span>
              <Button 
                variant="outline-success" 
                size="sm" 
                onClick={saveAppliedRulesAsNormalizationRules}
                disabled={saving}
              >
                {saving ? <Spinner size="sm" className="me-1" /> : <FaSave className="me-1" />}
                Save Custom Rules
              </Button>
            </Card.Header>
            <Card.Body>
              <Table striped size="sm">
                <thead>
                  <tr>
                    <th>Raw Key</th>
                    <th>Canonical Key</th>
                    <th>Matched Column</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {appliedRules.map((rule, index) => (
                    <tr key={index}>
                      <td><code>{rule.raw_key}</code></td>
                      <td><code className="text-success">{rule.canonical_key}</code></td>
                      <td><code className="text-primary">{rule.matched_column}</code></td>
                      <td>
                        <Badge bg={rule.type === 'existing' ? 'primary' : 'warning'}>
                          {rule.type}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <small className="text-muted">
                Only custom rules (marked as "custom" type) will be saved to your normalization rules database.
              </small>
            </Card.Body>
          </Card>
        )}

        {/* Unmapped Columns */}
        {unmappedColumns.length > 0 && (
          <Card className="mt-3">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <div>
                <FaExclamationTriangle className="text-warning me-2" />
                Unmapped Columns
              </div>
              <Button 
                variant="outline-primary" 
                size="sm" 
                onClick={addRulesFromUnmappedColumns}
              >
                <FaPlus className="me-1" />
                Create Rules
              </Button>
            </Card.Header>
            <Card.Body>
              <div className="d-flex flex-wrap gap-2 mb-2">
                {unmappedColumns.map(col => (
                  <Badge key={col} bg="warning" text="dark">{col}</Badge>
                ))}
              </div>
              <small className="text-muted">
                Click "Create Rules" to add these unmapped columns to your custom rules for mapping.
              </small>
            </Card.Body>
          </Card>
        )}
      </div>
    );
  };

  const renderCustomRules = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h6>Custom Normalization Rules</h6>
        <Button variant="outline-primary" size="sm" onClick={addCustomRule}>
          <FaPlus className="me-1" />
          Add Rule
        </Button>
      </div>

      {customRules.length === 0 ? (
        <Alert variant="info">
          <FaInfoCircle className="me-2" />
          No custom rules defined. Add rules to test how they would transform your data.
        </Alert>
      ) : (
        <div className="space-y-3">
          {customRules.map((rule, index) => (
            <Card key={index} className="mb-2">
              <Card.Body className="py-2">
                <Row>
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label size="sm">Raw Key</Form.Label>
                      <Form.Control
                        size="sm"
                        type="text"
                        value={rule.raw_key}
                        onChange={(e) => updateCustomRule(index, 'raw_key', e.target.value)}
                        placeholder="e.g., temp, temperature"
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label size="sm">Canonical Key</Form.Label>
                      <Form.Control
                        size="sm"
                        type="text"
                        value={rule.canonical_key}
                        onChange={(e) => updateCustomRule(index, 'canonical_key', e.target.value)}
                        placeholder="e.g., temperature"
                      />
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label size="sm">Ingestion ID</Form.Label>
                      <Form.Control
                        size="sm"
                        type="text"
                        value={rule.ingestion_id || ''}
                        onChange={(e) => updateCustomRule(index, 'ingestion_id', e.target.value)}
                        placeholder="Optional"
                      />
                    </Form.Group>
                  </Col>
                  <Col md={1} className="d-flex align-items-end">
                    <Button
                      variant="outline-danger"
                      size="sm"
                      onClick={() => removeCustomRule(index)}
                    >
                      <FaTrash />
                    </Button>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          ))}
        </div>
      )}

      {customRules.length > 0 && (
        <div className="mt-3 d-flex gap-2">
          <Button variant="outline-secondary" onClick={validateRules} disabled={loading || saving}>
            {loading ? <Spinner size="sm" className="me-1" /> : <FaCheck className="me-1" />}
            Validate Rules
          </Button>
          <Button variant="success" onClick={saveNormalizationRules} disabled={loading || saving}>
            {saving ? <Spinner size="sm" className="me-1" /> : <FaSave className="me-1" />}
            Save Rules
          </Button>
        </div>
      )}
    </div>
  );

  const renderValidationResults = () => {
    if (!validationResult) {
      return (
        <Alert variant="info">
          <FaInfoCircle className="me-2" />
          Define custom rules and click "Validate Rules" to check if they can be applied to your data.
        </Alert>
      );
    }

    return (
      <div>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h6>Validation Results</h6>
          <Badge bg={validationResult.overall_valid ? 'success' : 'danger'}>
            {validationResult.overall_valid ? 'All Valid' : 'Issues Found'}
          </Badge>
        </div>

        <Row className="mb-3">
          <Col md={4}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-primary">{validationResult.total_rules}</h5>
                <small>Total Rules</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-success">{validationResult.valid_rules}</h5>
                <small>Valid</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="text-center">
              <Card.Body>
                <h5 className="text-danger">{validationResult.invalid_rules}</h5>
                <small>Invalid</small>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Table striped size="sm">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Raw Key</th>
              <th>Canonical Key</th>
              <th>Status</th>
              <th>Issues</th>
            </tr>
          </thead>
          <tbody>
            {validationResult.validation_details.map((detail: any, index: number) => (
              <tr key={index}>
                <td>#{index + 1}</td>
                <td><code>{detail.raw_key}</code></td>
                <td><code>{detail.canonical_key}</code></td>
                <td>
                  <Badge bg={detail.valid ? 'success' : 'danger'}>
                    {detail.valid ? 'Valid' : 'Invalid'}
                  </Badge>
                </td>
                <td>
                  {detail.errors.length > 0 && (
                    <div>
                      {detail.errors.map((error: string, i: number) => (
                        <small key={i} className="text-danger d-block">{error}</small>
                      ))}
                    </div>
                  )}
                  {detail.warnings.length > 0 && (
                    <div>
                      {detail.warnings.map((warning: string, i: number) => (
                        <small key={i} className="text-warning d-block">{warning}</small>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    );
  };

  return (
    <Modal show={show} onHide={onHide} size="xl" centered>
      <Modal.Header closeButton>
        <Modal.Title>
          <FaEye className="me-2" />
          Normalization Preview
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && (
          <Alert variant="danger" dismissible onClose={() => setError('')}>
            {error}
          </Alert>
        )}
        
        {saveSuccess && (
          <Alert variant="success" dismissible onClose={() => setSaveSuccess('')}>
            {saveSuccess}
          </Alert>
        )}

        {/* Controls */}
        <Card className="mb-3">
          <Card.Body>
            <Row>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Ingestion ID Filter</Form.Label>
                  <Form.Select
                    value={selectedIngestionId}
                    onChange={(e) => setSelectedIngestionId(e.target.value)}
                    disabled={loading}
                  >
                    <option value="">
                      {loading ? 'Loading ingestion IDs...' : 'All Ingestion IDs'}
                    </option>
                    {(sampleData?.sample_ingestion_ids || []).map(id => (
                      <option key={id} value={id}>{id}</option>
                    ))}
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label>Sample Limit</Form.Label>
                  <Form.Control
                    type="number"
                    value={sampleLimit}
                    onChange={(e) => setSampleLimit(parseInt(e.target.value) || 100)}
                    min={1}
                    max={1000}
                  />
                </Form.Group>
              </Col>
              <Col md={5} className="d-flex align-items-end gap-2">
                <Button variant="primary" onClick={runPreview} disabled={loading}>
                  {loading ? <Spinner size="sm" className="me-1" /> : <FaPlay className="me-1" />}
                  Run Preview
                </Button>
                <Button variant="outline-secondary" onClick={loadSampleData} disabled={loading}>
                  Refresh Data
                </Button>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Tabs */}
        <Tabs activeKey={activeTab} onSelect={(k) => setActiveTab(k || 'preview')} className="mb-3">
          <Tab eventKey="data" title="Sample Data">
            {renderSampleDataTable()}
          </Tab>
          <Tab eventKey="rules" title="Custom Rules">
            {renderCustomRules()}
          </Tab>
          <Tab eventKey="preview" title="Preview Results">
            {renderPreviewResults()}
          </Tab>
          <Tab eventKey="validation" title="Validation">
            {renderValidationResults()}
          </Tab>
        </Tabs>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default NormalizationPreviewModal;
