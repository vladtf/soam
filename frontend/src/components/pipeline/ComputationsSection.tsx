import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, Table, Badge, Modal, Form, Row, Col, Spinner, Alert } from 'react-bootstrap';
import { toast } from 'react-toastify';
import {
  FaPlus, FaEdit, FaTrash, FaEye, FaCog, FaInfoCircle,
  FaTrophy, FaMedal, FaAward, FaStar, FaBell, FaBroadcastTower,
  FaRobot, FaTimes, FaSave, FaFileAlt, FaChartBar, FaShieldAlt, FaExclamationTriangle
} from 'react-icons/fa';
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
  checkComputationDependencies,
  analyzeComputationSensitivity,
  AnalyzeSensitivityResponse,
  DataSensitivity,
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
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [examplePreviewData, setExamplePreviewData] = useState<{ result: unknown[]; row_count: number } | null>(null);
  const [previewingExample, setPreviewingExample] = useState<string | null>(null);
  
  // Sensitivity analysis state
  const [sensitivityInfo, setSensitivityInfo] = useState<AnalyzeSensitivityResponse | null>(null);
  const [analyzingSensitivity, setAnalyzingSensitivity] = useState(false);

  // Debounced sensitivity analysis
  const analyzeSensitivity = useCallback(async (definition: Record<string, unknown>) => {
    if (!definition || Object.keys(definition).length === 0) {
      setSensitivityInfo(null);
      return;
    }
    
    setAnalyzingSensitivity(true);
    try {
      const result = await analyzeComputationSensitivity(definition);
      setSensitivityInfo(result);
    } catch (error) {
      console.error('Error analyzing sensitivity:', error);
      setSensitivityInfo(null);
    } finally {
      setAnalyzingSensitivity(false);
    }
  }, []);

  useEffect(() => {
    const loadExamples = async () => {
      try {
        setExamplesLoading(true);
        const exampleData = await fetchComputationExamples();
        setExamples(exampleData.examples);
      } catch (error) {
        console.error('Error loading examples:', error);
      } finally {
        setExamplesLoading(false);
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
    // Analyze sensitivity for the current definition
    if (computation.definition) {
      analyzeSensitivity(computation.definition);
    } else {
      setSensitivityInfo(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      // First check for dependencies
      const deps = await checkComputationDependencies(id);
      
      let confirmMessage = `Are you sure you want to delete the computation "${deps.computation.name}"?`;
      
      if (deps.has_dependencies) {
        const tileNames = deps.dependent_tiles.map(tile => `• ${tile.name} (${tile.viz_type})`).join('\n');
        confirmMessage = `⚠️ WARNING: The computation "${deps.computation.name}" is used by ${deps.dependent_tiles.length} dashboard tile(s):\n\n${tileNames}\n\nDeleting this computation will cause these tiles to show "Computation Deleted" errors.\n\nAre you sure you want to continue?`;
      }
      
      if (window.confirm(confirmMessage)) {
        await deleteComputation(id);
        toast.success('Computation deleted successfully');
        if (deps.has_dependencies) {
          toast.warning(`${deps.dependent_tiles.length} dashboard tile(s) will now show errors until updated`, {
            autoClose: 5000
          });
        }
        onComputationsChange();
      }
    } catch (error) {
      console.error('Error during computation deletion:', error);
      toast.error(extractDeleteErrorMessage(error));
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
    setSensitivityInfo(null); // Clear sensitivity for new computation
  };

  const useExample = (example: ComputationExample) => {
    setForm({
      ...form,
      name: example.title,
      dataset: example.dataset,
      definition: example.definition,
      description: example.description || '',
    });
    // Analyze sensitivity for the example definition
    analyzeSensitivity(example.definition);
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
            <FaPlus className="me-1" /> Add Computation
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
                          <>
                            <FaEye className="me-1" />
                            Preview
                          </>
                        )}
                      </Button>
                      <Button
                        variant="outline-primary"
                        size="sm"
                        className="me-1"
                        onClick={() => handleEdit(comp)}
                      >
                        <FaEdit className="me-1" />
                        Edit
                      </Button>
                      <Button
                        variant="outline-danger"
                        size="sm"
                        onClick={() => handleDelete(comp.id!)}
                      >
                        <FaTrash className="me-1" />
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
      <Modal show={showModal} onHide={() => { setShowModal(false); setSensitivityInfo(null); }} size="xl" centered>
        <Modal.Header closeButton>
          <Modal.Title>
            {editingId ? (
              <>
                <FaEdit className="me-2 text-primary" />
                Edit Computation
              </>
            ) : (
              <>
                <FaPlus className="me-2 text-primary" />
                Add New Computation
              </>
            )}
          </Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleSubmit}>
          <Modal.Body style={{ maxHeight: '80vh', overflowY: 'auto' }}>
            {/* Basic Information Section */}
            <div className="mb-4">
              <h6 className="text-primary mb-3">
                <FaInfoCircle className="me-2" />
                Basic Information
              </h6>
              <Row className="g-3">
                <Col md={8}>
                  <Form.Group>
                    <Form.Label className="fw-bold">Computation Name</Form.Label>
                    <Form.Control
                      type="text"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Enter a descriptive name for your computation..."
                      required
                      size="lg"
                    />
                    <Form.Text className="text-muted">
                      Choose a clear, descriptive name that explains what this computation does.
                    </Form.Text>
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label className="fw-bold">Dataset Source</Form.Label>
                    <Form.Control
                      as="select"
                      value={form.dataset}
                      onChange={(e) => setForm({ ...form, dataset: e.target.value as any })}
                      size="lg"
                    >
                      <option value="gold">
                        <FaTrophy className="me-1" />
                        Gold (Processed & Clean)
                      </option>
                      <option value="silver">
                        <FaMedal className="me-1" />
                        Silver (Normalized)
                      </option>
                      <option value="bronze">
                        <FaAward className="me-1" />
                        Bronze (Raw Data)
                      </option>
                      <option value="enriched">
                        <FaStar className="me-1" />
                        Enriched (Enhanced)
                      </option>
                      <option value="alerts">
                        <FaBell className="me-1" />
                        Alerts (Events)
                      </option>
                      <option value="sensors">
                        <FaBroadcastTower className="me-1" />
                        Sensors (Live Data)
                      </option>
                    </Form.Control>
                  </Form.Group>
                </Col>
              </Row>

              <Row className="mt-3">
                <Col>
                  <Form.Group>
                    <Form.Label className="fw-bold">Description</Form.Label>
                    <Form.Control
                      type="text"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                      placeholder="Describe what this computation analyzes or calculates..."
                      size="lg"
                    />
                    <Form.Text className="text-muted">
                      Explain the purpose and expected output of this computation.
                    </Form.Text>
                  </Form.Group>
                </Col>
              </Row>
            </div>

            {/* Definition Section */}
            <div className="mb-4">
              <h6 className="text-primary mb-3">
                <FaCog className="me-2" />
                Computation Definition
              </h6>
              <Form.Group>
                <Form.Label className="fw-bold d-flex justify-content-between align-items-center">
                  <span>JSON Definition</span>
                  <div className="d-flex gap-2">
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      onClick={() => {
                        try {
                          const formatted = JSON.stringify(form.definition, null, 2);
                          setForm({ ...form, definition: JSON.parse(formatted) });
                        } catch {
                          toast.error("Cannot format invalid JSON");
                        }
                      }}
                      title="Format JSON"
                    >
                      <FaCog className="me-1" />
                      Format
                    </Button>
                    <Button
                      variant="outline-info"
                      size="sm"
                      onClick={() => {
                        const example = {
                          "select": ["*"],
                          "where": {
                            "column": "temperature",
                            "operator": ">",
                            "value": 25
                          },
                          "orderBy": [{"column": "timestamp", "direction": "DESC"}],
                          "limit": 100
                        };
                        setForm({ ...form, definition: example });
                      }}
                      title="Load example template"
                    >
                      <FaFileAlt className="me-1" />
                      Example
                    </Button>
                  </div>
                </Form.Label>
                <Form.Control
                  as="textarea"
                  rows={18}
                  value={JSON.stringify(form.definition, null, 2)}
                  onChange={(e) => {
                    try {
                      const definition = JSON.parse(e.target.value);
                      setForm({ ...form, definition });
                      // Analyze sensitivity when definition changes
                      analyzeSensitivity(definition);
                    } catch {
                      // Invalid JSON, don't update
                      setSensitivityInfo(null);
                    }
                  }}
                  placeholder={`{
  "select": ["*"],
  "where": {
    "column": "temperature",
    "operator": ">",
    "value": 25
  },
  "orderBy": [{"column": "timestamp", "direction": "DESC"}],
  "limit": 100
}`}
                  style={{
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", "Courier New", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    resize: 'vertical',
                    minHeight: '280px',
                    maxHeight: '500px'
                  }}
                />
                <div className="d-flex justify-content-between align-items-start mt-2">
                  <Form.Text className="text-muted">
                    Define your computation using JSON syntax. Use select, where, orderBy, and limit clauses.
                    <br />
                    <strong><FaCog className="me-1" />Tip:</strong> Use the Format button to clean up your JSON, or drag the corner to resize the editor!
                  </Form.Text>
                  <div className="text-muted small">
                    {(() => {
                      const jsonText = JSON.stringify(form.definition, null, 2);
                      const isValid = (() => {
                        try { JSON.parse(jsonText); return true; } catch { return false; }
                      })();
                      return (
                        <>
                          Lines: {jsonText.split('\n').length} | 
                          Chars: {jsonText.length} |
                          <span className={isValid ? "text-success" : "text-danger"}>
                            {isValid ? " Valid JSON ✓" : " Invalid JSON ✗"}
                          </span>
                        </>
                      );
                    })()}
                  </div>
                </div>
              </Form.Group>
            </div>

            {/* Data Sensitivity Section */}
            <div className="mb-4">
              <h6 className="text-primary mb-3">
                <FaShieldAlt className="me-2" />
                Data Sensitivity
                {analyzingSensitivity && <Spinner animation="border" size="sm" className="ms-2" />}
              </h6>
              <div className="p-3 bg-light rounded">
                {sensitivityInfo ? (
                  <>
                    <div className="d-flex align-items-center gap-2 mb-3">
                      <span className="fw-bold">Calculated Sensitivity:</span>
                      <Badge 
                        bg={
                          sensitivityInfo.sensitivity === 'restricted' ? 'danger' :
                          sensitivityInfo.sensitivity === 'confidential' ? 'warning' :
                          sensitivityInfo.sensitivity === 'internal' ? 'info' : 'secondary'
                        }
                        className="text-uppercase"
                      >
                        {sensitivityInfo.sensitivity}
                      </Badge>
                    </div>
                    
                    {/* Custom Sensitivity Override */}
                    <Form.Group className="mb-3">
                      <Form.Label className="fw-bold">
                        Custom Sensitivity (Optional)
                      </Form.Label>
                      <Form.Select
                        value={form.sensitivity || ''}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                          const value = e.target.value as DataSensitivity | '';
                          setForm({ ...form, sensitivity: value || undefined });
                        }}
                        className="w-auto"
                      >
                        <option value="">Auto (use calculated)</option>
                        <option value="public">Public</option>
                        <option value="internal">Internal</option>
                        <option value="confidential">Confidential</option>
                        <option value="restricted">Restricted</option>
                      </Form.Select>
                      <Form.Text className="text-muted">
                        {form.sensitivity 
                          ? <>Overriding calculated sensitivity ({sensitivityInfo.sensitivity}) with: <strong className="text-uppercase">{form.sensitivity}</strong></>
                          : "Leave as 'Auto' to inherit sensitivity from source devices."
                        }
                      </Form.Text>
                    </Form.Group>
                    
                    {sensitivityInfo.warning && (
                      <Alert variant="warning" className="py-2 mb-2">
                        <FaExclamationTriangle className="me-2" />
                        {sensitivityInfo.warning}
                      </Alert>
                    )}
                    
                    {sensitivityInfo.source_devices.length > 0 && (
                      <div className="small text-muted">
                        <strong>Source Devices ({sensitivityInfo.source_devices.length}):</strong>
                        <div className="mt-1">
                          {sensitivityInfo.source_devices.slice(0, 5).map((device, idx) => (
                            <Badge key={idx} bg="light" text="dark" className="me-1 mb-1">
                              {device.name || device.ingestion_id}
                              <span className="ms-1 text-muted">({device.sensitivity})</span>
                            </Badge>
                          ))}
                          {sensitivityInfo.source_devices.length > 5 && (
                            <Badge bg="light" text="muted" className="me-1 mb-1">
                              +{sensitivityInfo.source_devices.length - 5} more
                            </Badge>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {sensitivityInfo.source_devices.length === 0 && (
                      <div className="small text-muted">
                        No specific devices referenced. Sensitivity is based on all accessible devices.
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-muted">
                    Enter a valid computation definition to analyze data sensitivity.
                  </div>
                )}
              </div>
            </div>

            {/* Settings Section */}
            <div className="mb-4">
              <h6 className="text-primary mb-3">
                <FaCog className="me-2" />
                Settings
              </h6>
              <Form.Group>
                <Form.Check
                  type="switch"
                  id="enabled-switch"
                  label="Enable this computation"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                <Form.Text className="text-muted">
                  {form.enabled
                    ? "This computation will be available for execution and dashboard tiles."
                    : "This computation will be saved but not available for execution."
                  }
                </Form.Text>
              </Form.Group>
            </div>

            {/* Examples Section */}
            {(examples.length > 0 || examplesLoading) && (
              <div className="mb-4">
                <h6 className="text-primary mb-3">
                  <FaChartBar className="me-2" />
                  Quick Start Examples
                </h6>
                <div className="p-3 bg-light rounded">
                  {examplesLoading ? (
                    <div className="text-center py-3">
                      <Spinner animation="border" variant="primary" size="sm" className="me-2" />
                      <span className="text-muted">Loading examples...</span>
                    </div>
                  ) : (
                    <>
                      <p className="text-muted mb-3">
                        Click any example to load it into the form, then customize it for your needs:
                      </p>
                      <div className="d-flex flex-wrap gap-2">
                        {examples.map((example, idx) => (
                          <div key={idx} className="d-flex gap-1">
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={() => useExample(example)}
                              className="fw-bold"
                            >
                              <FaFileAlt className="me-1" />
                              {example.title}
                            </Button>
                            <Button
                              variant="outline-info"
                              size="sm"
                              disabled={previewingExample === example.id}
                              onClick={() => handlePreviewExample(example.id)}
                              title="Preview this example"
                            >
                              {previewingExample === example.id ? (
                                <Spinner animation="border" size="sm" />
                              ) : (
                                <FaEye />
                              )}
                            </Button>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {examplePreviewData && !examplesLoading && (
                    <Card className="mt-3">
                      <Card.Header className="py-2 bg-info text-white">
                        <small className="fw-bold">
                          <FaChartBar className="me-1" />
                          Example Preview Results ({examplePreviewData.row_count} rows)
                        </small>
                      </Card.Header>
                      <Card.Body style={{ maxHeight: '250px', overflow: 'auto', fontSize: '13px' }}>
                        <pre className="mb-0 text-success">
                          {JSON.stringify(examplePreviewData.result, null, 2)}
                        </pre>
                      </Card.Body>
                    </Card>
                  )}
                </div>
              </div>
            )}
          </Modal.Body>
          <Modal.Footer className="d-flex justify-content-between">
            <div>
              {!editingId && copilotAvailable && (
                <Button
                  variant="outline-info"
                  onClick={() => setShowCopilot(true)}
                  className="fw-bold"
                  style={{ 
                    backgroundColor: '#ffffff'
                  }}
                >
                  <FaRobot className="me-2" />
                  Generate with AI Copilot
                </Button>
              )}
            </div>
            <div className="d-flex gap-2">
              <Button
                variant="outline-secondary"
                onClick={() => setShowModal(false)}
                size="lg"
              >
                <FaTimes className="me-1" />
                Cancel
              </Button>
              <Button
                variant="primary"
                type="submit"
                size="lg"
                className="fw-bold"
              >
                {editingId ? (
                  <>
                    <FaSave className="me-1" />
                    Update Computation
                  </>
                ) : (
                  <>
                    <FaPlus className="me-1" />
                    Create Computation
                  </>
                )}
              </Button>
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
