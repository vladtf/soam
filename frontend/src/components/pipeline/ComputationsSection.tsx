import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Badge, Modal, Form, Row, Col, Spinner } from 'react-bootstrap';
import { toast } from 'react-toastify';
import {
  ComputationDef,
  createComputation,
  updateComputation,
  deleteComputation,
  previewComputation,
  fetchComputationExamples,
  previewExampleComputation,
  ComputationExample,
  ComputationSuggestion,
  getCopilotHealth,
} from '../../api/backendRequests';
import { useAuth } from '../../context/AuthContext';
import { extractComputationErrorMessage, extractPreviewErrorMessage, extractDeleteErrorMessage } from '../../utils/errorHandling';
import CopilotAssistant from '../computations/CopilotAssistant';

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
  const [showCopilot, setShowCopilot] = useState(false);
  const [copilotAvailable, setCopilotAvailable] = useState(false);
  const [form, setForm] = useState<ComputationDef>(emptyComputation);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewingComputationId, setPreviewingComputationId] = useState<number | null>(null);
  const [examples, setExamples] = useState<ComputationExample[]>([]);
  const [examplePreviewData, setExamplePreviewData] = useState<{ result: unknown[]; row_count: number } | null>(null);
  const [previewingExample, setPreviewingExample] = useState<string | null>(null);

  useEffect(() => {
    const loadExamples = async () => {
      try {
        const exampleData = await fetchComputationExamples();
        setExamples(exampleData.examples);
      } catch (error) {
        console.error('Error loading examples:', error);
      }
    };

    const checkCopilotHealth = async () => {
      try {
        const health = await getCopilotHealth();
        console.log('Copilot health:', health);
        setCopilotAvailable(health.available);
      } catch (error) {
        console.error('Error checking copilot health:', error);
        setCopilotAvailable(false);
      }
    };

    loadExamples();
    checkCopilotHealth();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updateComputation(editingId, {
          ...form,
          updated_by: username,
        });
        toast.success('Computation updated successfully');
      } else {
        await createComputation({
          ...form,
          created_by: username,
        });
        toast.success('Computation created successfully');
      }
      setShowModal(false);
      setForm(emptyComputation);
      setEditingId(null);
      onComputationsChange();
    } catch (error) {
      console.error('Error saving computation:', error);
      toast.error(extractComputationErrorMessage(error));
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
        toast.success('Computation deleted successfully');
        onComputationsChange();
      } catch (error) {
        console.error('Error deleting computation:', error);
        toast.error(extractDeleteErrorMessage(error));
      }
    }
  };

  const handlePreview = async (computation: ComputationDef) => {
    if (!computation.id) return;

    setPreviewLoading(true);
    setPreviewingComputationId(computation.id);
    setPreviewData(null); // Clear previous preview data
    
    // Show loading toast
    toast.info(`🔄 Loading preview for "${computation.name}"...`, {
      toastId: `preview-${computation.id}`, // Prevent duplicate toasts
      autoClose: false, // Keep it until we dismiss it manually
    });

    try {
      const preview = await previewComputation(computation.id);
      setPreviewData(preview);
      
      // Dismiss loading toast and show success
      toast.dismiss(`preview-${computation.id}`);
      toast.success(`✅ Preview loaded for "${computation.name}"`);
    } catch (error) {
      console.error('Error previewing computation:', error);
      setPreviewData(null);
      
      // Dismiss loading toast and show error
      toast.dismiss(`preview-${computation.id}`);
      toast.error(extractPreviewErrorMessage(error));
    } finally {
      setPreviewLoading(false);
      setPreviewingComputationId(null);
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
      dataset: example.dataset,
      definition: example.definition,
      description: example.description || '',
    });
  };

  const handlePreviewExample = async (exampleId: string) => {
    setPreviewingExample(exampleId);
    try {
      const response = await previewExampleComputation(exampleId);
      setExamplePreviewData({ result: response.result, row_count: response.row_count });
    } catch (error) {
      console.error('Error previewing example:', error);
      setExamplePreviewData(null);
      toast.error(extractPreviewErrorMessage(error));
    } finally {
      setPreviewingExample(null);
    }
  };

  // Handler for copilot suggestions
  const handleCopilotSuggestion = (suggestion: ComputationSuggestion) => {
    setForm({
      ...emptyComputation,
      name: suggestion.title,
      dataset: suggestion.dataset,
      definition: suggestion.definition,
      description: suggestion.description,
    });
    setShowModal(true);
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
                    <td>
                      <strong>{comp.name}</strong>
                      {previewLoading && previewingComputationId === comp.id && (
                        <span className="ms-2 text-primary">
                          <Spinner as="span" animation="border" size="sm" />
                          <small className="ms-1">Previewing...</small>
                        </span>
                      )}
                    </td>
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
                        {previewLoading && previewingComputationId === comp.id ? (
                          <>
                            <Spinner as="span" animation="border" size="sm" className="me-1" />
                            Loading...
                          </>
                        ) : (
                          'Preview'
                        )}
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

          {(previewData || previewLoading) && (
            <Card className="mt-3">
              <Card.Header>
                {previewLoading ? (
                  <span className="d-flex align-items-center">
                    <Spinner as="span" animation="border" size="sm" className="me-2" />
                    Loading Preview Results...
                  </span>
                ) : (
                  'Preview Results'
                )}
              </Card.Header>
              <Card.Body>
                {previewLoading ? (
                  <div className="text-center py-4">
                    <Spinner animation="border" variant="primary" />
                    <p className="mt-3 text-muted">
                      Executing computation and fetching results...
                    </p>
                  </div>
                ) : previewData ? (
                  <pre style={{ maxHeight: '300px', overflow: 'auto' }}>
                    {JSON.stringify(previewData, null, 2)}
                  </pre>
                ) : (
                  <div className="text-center py-4 text-muted">
                    No preview data available
                  </div>
                )}
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
                    <option value="enriched">Enriched</option>
                    <option value="alerts">Alerts</option>
                    <option value="sensors">Sensors</option>
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
                      <div key={idx} className="d-flex gap-1">
                        <Button
                          variant="outline-secondary"
                          size="sm"
                          onClick={() => useExample(example)}
                        >
                          {example.title}
                        </Button>
                        <Button
                          variant="outline-info"
                          size="sm"
                          disabled={previewingExample === example.id}
                          onClick={() => handlePreviewExample(example.id)}
                        >
                          👁️
                        </Button>
                      </div>
                    ))}
                  </div>
                  {examplePreviewData && (
                    <Card className="mt-3">
                      <Card.Header className="py-2">
                        <small>Example Preview ({examplePreviewData.row_count} rows)</small>
                      </Card.Header>
                      <Card.Body style={{ maxHeight: '200px', overflow: 'auto', fontSize: '0.85rem' }}>
                        <pre className="mb-0">{JSON.stringify(examplePreviewData.result, null, 2)}</pre>
                      </Card.Body>
                    </Card>
                  )}
                </Col>
              </Row>
            )}
          </Modal.Body>
          <Modal.Footer>
            <div className="d-flex justify-content-between w-100">
              <div>
                {!editingId && copilotAvailable && (
                  <Button
                    variant="info"
                    onClick={() => setShowCopilot(true)}
                    className="me-2"
                  >
                    🤖 Generate with Copilot
                  </Button>
                )}
              </div>
              <div>
                <Button variant="secondary" onClick={() => setShowModal(false)} className="me-2">
                  Cancel
                </Button>
                <Button variant="primary" type="submit">
                  {editingId ? 'Update' : 'Create'} Computation
                </Button>
              </div>
            </div>
          </Modal.Footer>
        </Form>
      </Modal>

      {/* Copilot Assistant */}
      <CopilotAssistant
        show={showCopilot}
        onHide={() => setShowCopilot(false)}
        onAcceptSuggestion={handleCopilotSuggestion}
      />
    </>
  );
};

export default ComputationsSection;
