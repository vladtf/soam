import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Badge, Modal, Form, Row, Col } from 'react-bootstrap';
import {
  ComputationDef,
  createComputation,
  updateComputation,
  deleteComputation,
  previewComputation,
  fetchComputationExamples,
  ComputationExample,
} from '../../api/backendRequests';
import { useAuth } from '../../context/AuthContext';

interface ComputationsSectionProps {
  computations: ComputationDef[];
  activePartition: string;
  onComputationsChange: () => void;
}

const emptyComputation: ComputationDef = {
  name: '',
  dataset: 'gold',
  definition: {},
  description: '',
  enabled: true,
};

const ComputationsSection: React.FC<ComputationsSectionProps> = ({
  computations,
  activePartition,
  onComputationsChange,
}) => {
  const { username } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<ComputationDef>(emptyComputation);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [examples, setExamples] = useState<ComputationExample[]>([]);

  useEffect(() => {
    const loadExamples = async () => {
      try {
        const exampleData = await fetchComputationExamples();
        setExamples(exampleData.examples);
      } catch (error) {
        console.error('Error loading examples:', error);
      }
    };
    loadExamples();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updateComputation(editingId, {
          ...form,
          updated_by: username,
        });
      } else {
        await createComputation({
          ...form,
          created_by: username,
        });
      }
      setShowModal(false);
      setForm(emptyComputation);
      setEditingId(null);
      onComputationsChange();
    } catch (error) {
      console.error('Error saving computation:', error);
    }
  };

  const handleEdit = (computation: ComputationDef) => {
    setForm(computation);
    setEditingId(computation.id || null);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this computation?')) {
      try {
        await deleteComputation(id);
        onComputationsChange();
      } catch (error) {
        console.error('Error deleting computation:', error);
      }
    }
  };

  const handlePreview = async (computation: ComputationDef) => {
    if (!computation.id) return;
    
    setPreviewLoading(true);
    try {
      const preview = await previewComputation(computation.id);
      setPreviewData(preview);
    } catch (error) {
      console.error('Error previewing computation:', error);
      setPreviewData(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleAddNew = () => {
    setForm({
      ...emptyComputation,
      description: activePartition ? `Computation for ${activePartition}` : '',
    });
    setEditingId(null);
    setShowModal(true);
  };

  const useExample = (example: ComputationExample) => {
    setForm({
      ...form,
      name: example.title,
      definition: example.definition,
      description: example.description || '',
    });
  };

  // Helper function to render 'Updated by' info
  const renderUpdatedBy = (comp: ComputationDef) => {
    if (
      comp.updated_by &&
      comp.created_by &&
      comp.updated_by !== comp.created_by
    ) {
      return (
        <div className="small text-muted mt-1">
          Updated by: {comp.updated_by}
        </div>
      );
    }
    return null;
  };

  return (
    <>
      <Card>
        <Card.Header className="d-flex justify-content-between align-items-center">
          <div>
            <h5 className="mb-0">Computations</h5>
            <small className="text-muted">
              {activePartition ? `Related to ${activePartition}` : 'All computations'}
            </small>
          </div>
          <Button variant="primary" size="sm" onClick={handleAddNew}>
            + Add Computation
          </Button>
        </Card.Header>
        <Card.Body>
          {computations.length === 0 ? (
            <div className="text-center py-4">
              <p className="text-muted">No computations found.</p>
              <Button variant="outline-primary" onClick={handleAddNew}>
                Create First Computation
              </Button>
            </div>
          ) : (
            <Table responsive hover>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Dataset</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th>Created By</th>
                  <th>Last Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {computations.map((comp) => (
                  <tr key={comp.id}>
                    <td><strong>{comp.name}</strong></td>
                    <td>
                      <Badge bg="info">{comp.dataset}</Badge>
                    </td>
                    <td className="text-truncate" style={{ maxWidth: '200px' }}>
                      {comp.description}
                    </td>
                    <td>
                      <Badge bg={comp.enabled ? 'success' : 'secondary'}>
                        {comp.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                    </td>
                    <td>
                      <Badge bg="info">
                        {comp.created_by || 'unknown'}
                      </Badge>
                      {renderUpdatedBy(comp)}
                    </td>
                    <td className="small text-muted">
                      {comp.updated_at ? new Date(comp.updated_at).toLocaleString() : 
                       comp.created_at ? new Date(comp.created_at).toLocaleString() : '-'}
                    </td>
                    <td>
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        className="me-1"
                        onClick={() => handlePreview(comp)}
                        disabled={previewLoading}
                      >
                        Preview
                      </Button>
                      <Button
                        variant="outline-primary"
                        size="sm"
                        className="me-1"
                        onClick={() => handleEdit(comp)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="outline-danger"
                        size="sm"
                        onClick={() => handleDelete(comp.id!)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}

          {previewData && (
            <Card className="mt-3">
              <Card.Header>Preview Results</Card.Header>
              <Card.Body>
                <pre style={{ maxHeight: '300px', overflow: 'auto' }}>
                  {JSON.stringify(previewData, null, 2)}
                </pre>
              </Card.Body>
            </Card>
          )}
        </Card.Body>
      </Card>

      {/* Add/Edit Modal */}
      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{editingId ? 'Edit' : 'Add'} Computation</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleSubmit}>
          <Modal.Body>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Name</Form.Label>
                  <Form.Control
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Dataset</Form.Label>
                  <Form.Control
                    as="select"
                    value={form.dataset}
                    onChange={(e) => setForm({ ...form, dataset: e.target.value as any })}
                  >
                    <option value="gold">Gold</option>
                    <option value="silver">Silver</option>
                    <option value="bronze">Bronze</option>
                  </Form.Control>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col>
                <Form.Group className="mb-3">
                  <Form.Label>Description</Form.Label>
                  <Form.Control
                    type="text"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col>
                <Form.Group className="mb-3">
                  <Form.Label>Definition (JSON)</Form.Label>
                  <Form.Control
                    as="textarea"
                    rows={6}
                    value={JSON.stringify(form.definition, null, 2)}
                    onChange={(e) => {
                      try {
                        const definition = JSON.parse(e.target.value);
                        setForm({ ...form, definition });
                      } catch {
                        // Invalid JSON, don't update
                      }
                    }}
                    style={{ fontFamily: 'monospace' }}
                  />
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col>
                <Form.Group>
                  <Form.Check
                    type="switch"
                    id="enabled-switch"
                    label="Enable this computation"
                    checked={form.enabled}
                    onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                  />
                </Form.Group>
              </Col>
            </Row>

            {examples.length > 0 && (
              <Row className="mt-3">
                <Col>
                  <h6>Examples:</h6>
                  <div className="d-flex flex-wrap gap-2">
                    {examples.map((example, idx) => (
                      <Button
                        key={idx}
                        variant="outline-secondary"
                        size="sm"
                        onClick={() => useExample(example)}
                      >
                        {example.title}
                      </Button>
                    ))}
                  </div>
                </Col>
              </Row>
            )}
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              {editingId ? 'Update' : 'Create'} Computation
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </>
  );
};

export default ComputationsSection;
