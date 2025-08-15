import React, { useState } from 'react';
import { Card, Button, Table, Badge, Form, Row, Col, Modal } from 'react-bootstrap';
import {
  NormalizationRule,
  createNormalizationRule,
  updateNormalizationRule,
  deleteNormalizationRule,
  SensorData,
} from '../../api/backendRequests';

interface NormalizationRulesSectionProps {
  rules: NormalizationRule[];
  activePartition: string;
  partitions: string[];
  onRulesChange: () => void;
  sampleData?: SensorData[];
}

const emptyForm = { ingestion_id: '', raw_key: '', canonical_key: '', enabled: true };

const NormalizationRulesSection: React.FC<NormalizationRulesSectionProps> = ({
  rules,
  activePartition,
  partitions,
  onRulesChange,
  sampleData = [],
}) => {
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [errors, setErrors] = useState<{ ingestion_id?: string; raw_key?: string; canonical_key?: string }>({});

  const validateForm = () => {
    const newErrors: typeof errors = {};
    if (!form.ingestion_id.trim()) newErrors.ingestion_id = 'Ingestion ID is required';
    if (!form.raw_key.trim()) newErrors.raw_key = 'Raw key is required';
    if (!form.canonical_key.trim()) newErrors.canonical_key = 'Canonical key is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    try {
      if (editingId) {
        await updateNormalizationRule(editingId, {
          ingestion_id: form.ingestion_id.trim(),
          canonical_key: form.canonical_key.trim(),
          enabled: form.enabled,
        });
      } else {
        await createNormalizationRule({
          ingestion_id: form.ingestion_id.trim(),
          raw_key: form.raw_key.trim(),
          canonical_key: form.canonical_key.trim(),
          enabled: form.enabled,
        });
      }
      setShowModal(false);
      setForm(emptyForm);
      setEditingId(null);
      onRulesChange();
    } catch (error) {
      console.error('Error saving rule:', error);
    }
  };

  const handleEdit = (rule: NormalizationRule) => {
    setForm({
      ingestion_id: rule.ingestion_id || '',
      raw_key: rule.raw_key,
      canonical_key: rule.canonical_key,
      enabled: rule.enabled,
    });
    setEditingId(rule.id);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this rule?')) {
      try {
        await deleteNormalizationRule(id);
        onRulesChange();
      } catch (error) {
        console.error('Error deleting rule:', error);
      }
    }
  };

  const handleAddNew = () => {
    setForm({ ...emptyForm, ingestion_id: activePartition });
    setEditingId(null);
    setShowModal(true);
  };

  return (
    <>
      <Card>
        <Card.Header className="d-flex justify-content-between align-items-center">
          <div>
            <h5 className="mb-0">Normalization Rules</h5>
            <small className="text-muted">
              {activePartition ? `Showing rules for ${activePartition}` : 'Showing all rules'}
            </small>
          </div>
          <Button variant="primary" size="sm" onClick={handleAddNew}>
            + Add Rule
          </Button>
        </Card.Header>
        <Card.Body>
          {rules.length === 0 ? (
            <div className="text-center py-4">
              <p className="text-muted">No normalization rules found for this partition.</p>
              <Button variant="outline-primary" onClick={handleAddNew}>
                Create First Rule
              </Button>
            </div>
          ) : (
            <Table responsive hover>
              <thead>
                <tr>
                  <th>Ingestion ID</th>
                  <th>Raw Key</th>
                  <th>Canonical Key</th>
                  <th>Status</th>
                  <th>Applied</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      <Badge bg="secondary">{rule.ingestion_id || 'Global'}</Badge>
                    </td>
                    <td><code>{rule.raw_key}</code></td>
                    <td><code>{rule.canonical_key}</code></td>
                    <td>
                      <Badge bg={rule.enabled ? 'success' : 'secondary'}>
                        {rule.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                    </td>
                    <td>{rule.applied_count || 0}x</td>
                    <td>
                      <Button
                        variant="outline-primary"
                        size="sm"
                        className="me-1"
                        onClick={() => handleEdit(rule)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="outline-danger"
                        size="sm"
                        onClick={() => handleDelete(rule.id)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      {/* Add/Edit Modal */}
      <Modal show={showModal} onHide={() => setShowModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>{editingId ? 'Edit' : 'Add'} Normalization Rule</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleSubmit}>
          <Modal.Body>
            <Row>
              <Col>
                <Form.Group className="mb-3">
                  <Form.Label>Ingestion ID</Form.Label>
                  <Form.Control
                    as="select"
                    value={form.ingestion_id}
                    isInvalid={!!errors.ingestion_id}
                    onChange={(e) => setForm({ ...form, ingestion_id: e.target.value })}
                    required
                  >
                    <option value="">Select Partition...</option>
                    {partitions.map((partition) => (
                      <option key={partition} value={partition}>
                        {partition}
                      </option>
                    ))}
                  </Form.Control>
                  <Form.Control.Feedback type="invalid">{errors.ingestion_id}</Form.Control.Feedback>
                </Form.Group>
              </Col>
            </Row>

            {!editingId && sampleData.length > 0 && (
              <Row>
                <Col>
                  <div className="bg-body-secondary p-3 rounded mb-3">
                    <h6 className="small mb-2">💡 Available Columns in Your Data:</h6>
                    <div className="d-flex flex-wrap gap-1">
                      {Array.from(new Set(
                        sampleData.flatMap(row => Object.keys(row as Record<string, unknown>))
                      )).map(col => (
                        <Badge
                          key={col}
                          bg="outline-primary"
                          className="cursor-pointer"
                          style={{ cursor: 'pointer' }}
                          onClick={() => setForm({ ...form, raw_key: col })}
                        >
                          {col}
                        </Badge>
                      ))}
                    </div>
                    <small className="text-muted mt-1 d-block">
                      Click a column name to use it as the raw key
                    </small>
                  </div>
                </Col>
              </Row>
            )}

            {!editingId && (
              <Row>
                <Col>
                  <Form.Group className="mb-3">
                    <Form.Label>Raw Key</Form.Label>
                    <Form.Control
                      type="text"
                      placeholder="e.g., temp or sensor_id"
                      value={form.raw_key}
                      isInvalid={!!errors.raw_key}
                      onChange={(e) => setForm({ ...form, raw_key: e.target.value })}
                      required
                    />
                    <Form.Text className="text-muted">
                      Original column name from incoming data
                    </Form.Text>
                    <Form.Control.Feedback type="invalid">{errors.raw_key}</Form.Control.Feedback>
                  </Form.Group>
                </Col>
              </Row>
            )}

            <Row>
              <Col>
                <Form.Group className="mb-3">
                  <Form.Label>Canonical Key</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., temperature or sensorId"
                    value={form.canonical_key}
                    isInvalid={!!errors.canonical_key}
                    onChange={(e) => setForm({ ...form, canonical_key: e.target.value })}
                    required
                  />
                  <Form.Text className="text-muted">
                    Standardized column name for processing
                  </Form.Text>
                  <Form.Control.Feedback type="invalid">{errors.canonical_key}</Form.Control.Feedback>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col>
                <Form.Group>
                  <Form.Check
                    type="switch"
                    id="enabled-switch"
                    label="Enable this rule"
                    checked={form.enabled}
                    onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                  />
                </Form.Group>
              </Col>
            </Row>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              {editingId ? 'Update' : 'Create'} Rule
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </>
  );
};

export default NormalizationRulesSection;
