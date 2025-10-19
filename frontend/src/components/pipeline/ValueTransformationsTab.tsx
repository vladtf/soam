import React, { useState, useEffect } from 'react';
import { Container, Card, Table, Button, Modal, Form, Alert, Badge, Spinner, Row, Col } from 'react-bootstrap';
import {
  listValueTransformationRules,
  createValueTransformationRule,
  updateValueTransformationRule,
  deleteValueTransformationRule,
  toggleValueTransformationRule,
  getValueTransformationTypes,
  ValueTransformationRule,
  ValueTransformationRuleCreatePayload,
  ValueTransformationRuleUpdatePayload,
  getIngestorCurrentMetadata,
  getIngestorDatasetSchema,
  SchemaField
} from '../../api/backendRequests';

interface TransformationTypeDefinition {
  type: string;
  description: string;
  configSchema: Record<string, any>;
  examples: Array<{
    name: string;
    config: Record<string, any>;
    description: string;
  }>;
}

// Form state interface with string for textarea input
interface ValueTransformationFormData {
  field_name: string;
  transformation_type: 'filter' | 'aggregate' | 'convert' | 'validate';
  transformation_config: string; // String for textarea input
  order_priority: number;
  enabled: boolean;
  created_by: string;
  updated_by?: string;
  ingestion_id?: string | null;
}

interface ValueTransformationsTabProps {
  activePartition?: string;
}

const ValueTransformationsTab: React.FC<ValueTransformationsTabProps> = ({
  activePartition
}) => {
  const [rules, setRules] = useState<ValueTransformationRule[]>([]);
  const [transformationTypes, setTransformationTypes] = useState<Record<string, TransformationTypeDefinition>>({});
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const [loadingFields, setLoadingFields] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState<ValueTransformationRule | null>(null);
  const [formData, setFormData] = useState<ValueTransformationFormData>({
    field_name: '',
    transformation_type: 'filter',
    transformation_config: '',
    order_priority: 100,
    enabled: true,
    created_by: 'user'
  });

  useEffect(() => {
    loadData();
    loadAvailableFields();
  }, []);

  const loadAvailableFields = async () => {
    try {
      setLoadingFields(true);
      const currentMetadata = await getIngestorCurrentMetadata();
      
      // Extract all unique field names from all datasets
      const allFields = new Set<string>();
      
      for (const ingestionId of Object.keys(currentMetadata)) {
        try {
          const schemaData = await getIngestorDatasetSchema(ingestionId);
          schemaData.schema_fields.forEach((field: SchemaField) => {
            allFields.add(field.name);
          });
        } catch (err) {
          // Skip datasets that can't be fetched (might be old/inactive)
          console.warn(`Could not fetch schema for ${ingestionId}:`, err);
        }
      }
      
      // Convert to sorted array
      const fieldArray = Array.from(allFields).sort();
      setAvailableFields(fieldArray);
    } catch (err) {
      console.error('Error loading available fields:', err);
      // Don't set error state - this is optional functionality
    } finally {
      setLoadingFields(false);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const [rulesData, typesData] = await Promise.all([
        listValueTransformationRules(),
        getValueTransformationTypes()
      ]);
      setRules(rulesData);
      setTransformationTypes(typesData);
      setError(null);
    } catch (err) {
      setError('Failed to load value transformation rules');
      console.error('Error loading data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingRule(null);
    setError(null);
    setFormData({
      field_name: '',
      transformation_type: 'filter',
      transformation_config: '',
      order_priority: 100,
      enabled: true,
      created_by: 'user'
    });
    setShowModal(true);
  };

  const handleEdit = (rule: ValueTransformationRule) => {
    setEditingRule(rule);
    setError(null);
    setFormData({
      ingestion_id: rule.ingestion_id,
      field_name: rule.field_name,
      transformation_type: rule.transformation_type,
      transformation_config: rule.transformation_config,
      order_priority: rule.order_priority,
      enabled: rule.enabled,
      created_by: rule.created_by,
      updated_by: 'user'
    });
    setShowModal(true);
  };

  const getConfigPlaceholder = (transformationType: string): string => {
    const placeholders: Record<string, string> = {
      filter: '{\n  "operator": "gt",\n  "value": 25\n}',
      aggregate: '{\n  "function": "avg",\n  "window": "1h"\n}',
      convert: '{\n  "operation": "type_conversion",\n  "target_type": "float",\n  "default_value": 0.0\n}',
      validate: '{\n  "validation_rules": [\n    {"rule": "not_null"}\n  ]\n}'
    };
    return placeholders[transformationType] || '{\n  "key": "value"\n}';
  };

  const handleSave = async () => {
    try {
      // Parse the transformation_config JSON string
      let parsedConfig;
      try {
        parsedConfig = JSON.parse(formData.transformation_config || '{}');
      } catch (parseError) {
        setError('Invalid JSON configuration. Please check your syntax.');
        return;
      }

      // Validate required fields based on transformation type
      const requiredFields: Record<string, string[]> = {
        filter: ['operator', 'value'],
        aggregate: ['function', 'window'],
        convert: ['operation'],
        validate: ['validation_rules']
      };

      const required = requiredFields[formData.transformation_type] || [];
      let missing = required.filter(field => !(field in parsedConfig));
      
      // Special validation for convert type based on operation
      if (formData.transformation_type === 'convert' && parsedConfig.operation) {
        if (parsedConfig.operation === 'type_conversion') {
          if (!parsedConfig.target_type) {
            missing.push('target_type');
          }
        } else if (parsedConfig.operation === 'mathematical') {
          if (!parsedConfig.math_operation) {
            missing.push('math_operation');
          }
          if (!parsedConfig.operand && !parsedConfig.operand_field) {
            missing.push('operand (or operand_field)');
          }
        }
      }
      
      if (missing.length > 0) {
        setError(`Missing required configuration fields for ${formData.transformation_type}: ${missing.join(', ')}. Please use one of the examples below or check the documentation.`);
        return;
      }

      // Prepare the payload with parsed config
      const payload = {
        ...formData,
        transformation_config: parsedConfig
      };

      if (editingRule) {
        await updateValueTransformationRule(editingRule.id, payload as ValueTransformationRuleUpdatePayload);
      } else {
        await createValueTransformationRule(payload as ValueTransformationRuleCreatePayload);
      }
      setError(null);
      setShowModal(false);
      await loadData();
    } catch (err) {
      setError('Failed to save transformation rule');
      console.error('Error saving rule:', err);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this transformation rule?')) {
      try {
        await deleteValueTransformationRule(id);
        await loadData();
      } catch (err) {
        setError('Failed to delete transformation rule');
        console.error('Error deleting rule:', err);
      }
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await toggleValueTransformationRule(id);
      await loadData();
    } catch (err) {
      setError('Failed to toggle transformation rule');
      console.error('Error toggling rule:', err);
    }
  };

  const getTypeColor = (type: string) => {
    const colors = {
      filter: 'primary',
      aggregate: 'success',
      convert: 'warning',
      validate: 'danger'
    };
    return colors[type as keyof typeof colors] || 'secondary';
  };

  const renderConfigPreview = (config: string) => {
    try {
      const parsed = JSON.parse(config);
      return <code>{JSON.stringify(parsed, null, 2)}</code>;
    } catch {
      return <code>{config}</code>;
    }
  };

  const renderExamples = (type: string) => {
    const typeData = transformationTypes[type];
    if (!typeData?.examples) return null;

    return (
      <div className="mt-3">
        <h6>Examples:</h6>
        {typeData.examples.map((example, index) => (
          <Card key={index} className="mb-2" style={{ fontSize: '0.9em' }}>
            <Card.Body className="py-2">
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <strong>{example.name}</strong>
                  <div className="text-muted small">{example.description}</div>
                </div>
                <Button
                  size="sm"
                  variant="outline-primary"
                  onClick={() => setFormData({
                    ...formData,
                    transformation_config: JSON.stringify(example.config, null, 2)
                  })}
                >
                  Use
                </Button>
              </div>
              <pre className="mb-0 mt-2" style={{ fontSize: '0.8em' }}>
                {JSON.stringify(example.config, null, 2)}
              </pre>
            </Card.Body>
          </Card>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <Container fluid className="p-0">
        <div className="d-flex justify-content-center p-4">
          <Spinner animation="border" />
        </div>
      </Container>
    );
  }

  return (
    <Container fluid className="p-0">
      <div className="mb-3">
        <h5>Value Transformations</h5>
        <p className="text-muted">
          Configure data value transformations to filter, aggregate, convert, and validate incoming sensor data 
          before it's processed by the enrichment pipeline.
          {activePartition && (
            <> Currently viewing partition: <code>{activePartition}</code></>
          )}
        </p>
      </div>

      <Row>
        <Col>
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h5 className="mb-0">Value Transformation Rules</h5>
              <Button variant="primary" onClick={handleCreate}>
                Add Transformation Rule
              </Button>
            </Card.Header>
            <Card.Body>
              <Table striped bordered hover responsive>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Field Name</th>
                    <th>Type</th>
                    <th>Ingestion ID</th>
                    <th>Priority</th>
                    <th>Enabled</th>
                    <th>Applied Count</th>
                    <th>Configuration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="text-center text-muted">
                        No transformation rules found. Create your first rule to get started.
                      </td>
                    </tr>
                  ) : (
                    rules.map((rule) => (
                      <tr key={rule.id}>
                        <td>{rule.id}</td>
                        <td><code>{rule.field_name}</code></td>
                        <td>
                          <Badge bg={getTypeColor(rule.transformation_type)}>
                            {rule.transformation_type}
                          </Badge>
                        </td>
                        <td>
                          {rule.ingestion_id ? (
                            <code>{rule.ingestion_id}</code>
                          ) : (
                            <span className="text-muted">Global</span>
                          )}
                        </td>
                        <td>{rule.order_priority}</td>
                        <td>
                          <Badge bg={rule.enabled ? 'success' : 'secondary'}>
                            {rule.enabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                        </td>
                        <td>{rule.applied_count}</td>
                        <td>
                          <details>
                            <summary className="text-primary" style={{ cursor: 'pointer' }}>
                              View Config
                            </summary>
                            <div className="mt-2">
                              {renderConfigPreview(rule.transformation_config)}
                            </div>
                          </details>
                        </td>
                        <td>
                          <div className="d-flex gap-1">
                            <Button
                              size="sm"
                              variant={rule.enabled ? 'outline-warning' : 'outline-success'}
                              onClick={() => handleToggle(rule.id)}
                              title={rule.enabled ? 'Disable rule' : 'Enable rule'}
                            >
                              {rule.enabled ? '⏸️ Pause' : '▶️ Enable'}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline-primary"
                              onClick={() => handleEdit(rule)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline-danger"
                              onClick={() => handleDelete(rule.id)}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Create/Edit Modal */}
      <Modal show={showModal} onHide={() => { setShowModal(false); setError(null); }} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            {editingRule ? 'Edit Transformation Rule' : 'Create Transformation Rule'}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}
          
          {/* Action Buttons */}
          <div className="d-flex justify-content-end gap-2 mb-3">
            <Button variant="secondary" onClick={() => { setShowModal(false); setError(null); }}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave}>
              {editingRule ? 'Update' : 'Create'} Rule
            </Button>
          </div>
          
          <Form>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <div className="d-flex align-items-center justify-content-between">
                    <Form.Label>Field Name *</Form.Label>
                    {availableFields.length > 0 && (
                      <Button 
                        size="sm" 
                        variant="outline-secondary" 
                        onClick={loadAvailableFields}
                        disabled={loadingFields}
                      >
                        {loadingFields ? <Spinner size="sm" /> : '🔄'} Refresh
                      </Button>
                    )}
                  </div>
                  {availableFields.length > 0 ? (
                    <>
                      <Form.Select
                        value={availableFields.includes(formData.field_name) ? formData.field_name : '__custom__'}
                        onChange={(e) => {
                          if (e.target.value === '__custom__') {
                            setFormData({ ...formData, field_name: '' });
                          } else {
                            setFormData({ ...formData, field_name: e.target.value });
                          }
                        }}
                      >
                        <option value="">Select a field...</option>
                        {availableFields.map(field => (
                          <option key={field} value={field}>{field}</option>
                        ))}
                        <option value="__custom__">🖊️ Enter custom field name</option>
                      </Form.Select>
                      
                      {/* Show text input when custom is selected or field is not in list */}
                      {(!availableFields.includes(formData.field_name) || formData.field_name === '') && (
                        <Form.Control
                          type="text"
                          value={formData.field_name || ''}
                          onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                          placeholder="Enter custom field name (e.g., temperature, humidity)"
                          className="mt-2"
                        />
                      )}
                    </>
                  ) : (
                    <Form.Control
                      type="text"
                      value={formData.field_name || ''}
                      onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                      placeholder={loadingFields ? "Loading field names..." : "e.g., temperature, humidity"}
                      disabled={loadingFields}
                    />
                  )}
                  <Form.Text className="text-muted">
                    {availableFields.length > 0 
                      ? `Choose from ${availableFields.length} recently ingested fields or enter a custom name`
                      : "The field name to apply the transformation to"
                    }
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Ingestion ID</Form.Label>
                  <Form.Control
                    type="text"
                    value={formData.ingestion_id || ''}
                    onChange={(e) => setFormData({ ...formData, ingestion_id: e.target.value || null })}
                    placeholder="Leave empty for global rule"
                  />
                  <Form.Text className="text-muted">
                    Specific ingestion ID or leave empty for global rule
                  </Form.Text>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Transformation Type *</Form.Label>
                  <Form.Select
                    value={formData.transformation_type || 'filter'}
                    onChange={(e) => setFormData({ 
                      ...formData, 
                      transformation_type: e.target.value as any,
                      transformation_config: ''
                    })}
                  >
                    <option value="filter">Filter</option>
                    <option value="aggregate">Aggregate</option>
                    <option value="convert">Convert</option>
                    <option value="validate">Validate</option>
                  </Form.Select>
                  {transformationTypes[formData.transformation_type || 'filter'] && (
                    <Form.Text className="text-muted">
                      {transformationTypes[formData.transformation_type || 'filter'].description}
                    </Form.Text>
                  )}
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group className="mb-3">
                  <Form.Label>Priority</Form.Label>
                  <Form.Control
                    type="number"
                    value={formData.order_priority || 100}
                    onChange={(e) => setFormData({ ...formData, order_priority: parseInt(e.target.value) })}
                    min="1"
                    max="1000"
                  />
                  <Form.Text className="text-muted">
                    Lower numbers run first
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group className="mb-3">
                  <Form.Label>Status</Form.Label>
                  <Form.Check
                    type="switch"
                    id="enabled-switch"
                    label="Enabled"
                    checked={formData.enabled || false}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  />
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3">
              <Form.Label>Transformation Configuration *</Form.Label>
              <Form.Control
                as="textarea"
                rows={8}
                value={formData.transformation_config || ''}
                onChange={(e) => setFormData({ ...formData, transformation_config: e.target.value })}
                placeholder={getConfigPlaceholder(formData.transformation_type)}
                style={{ fontFamily: 'monospace', fontSize: '0.9em' }}
              />
              <Form.Text className="text-muted">
                JSON configuration object. Required fields vary by type - see examples below.
              </Form.Text>
            </Form.Group>

            {/* Examples section */}
            {formData.transformation_type && renderExamples(formData.transformation_type)}
          </Form>
        </Modal.Body>
      </Modal>
    </Container>
  );
};

export default ValueTransformationsTab;