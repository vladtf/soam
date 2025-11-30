import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { Modal, Row, Col, Form, Alert, Button, Card, Spinner, Badge } from 'react-bootstrap';
import { toast } from 'react-toastify';
import { 
  FaPlus, FaEdit, FaEye, FaLightbulb, FaInfoCircle, FaCog, 
  FaToggleOn, FaTrophy, FaMedal, FaAward, FaStar, FaBell, 
  FaBroadcastTower, FaTimes, FaSave, FaFileAlt, FaChartBar,
  FaShieldAlt, FaExclamationTriangle
} from 'react-icons/fa';
import WithTooltip from '../../components/WithTooltip';
import type { ComputationDef, ComputationExample, AnalyzeSensitivityResponse } from '../../api/backendRequests';
import { previewExampleComputation, analyzeComputationSensitivity } from '../../api/backendRequests';
import type { SchemaMap } from './DefinitionValidator';
import { validateDefinition } from './DefinitionValidator';
import { extractPreviewErrorMessage } from '../../utils/errorHandling';

interface Props {
  show: boolean;
  editing: ComputationDef | null;
  setEditing: (updater: (prev: ComputationDef | null) => ComputationDef | null) => void;
  sources: string[];
  examples: ComputationExample[];
  schemas: SchemaMap;
  onClose: () => void;
  onSave: () => Promise<void>;
}

const EditorModal: React.FC<Props> = ({ show, editing, setEditing, sources, examples, schemas, onClose, onSave }) => {
  const [defText, setDefText] = useState<string>('{}');
  const [defValid, setDefValid] = useState<boolean>(true);
  const [defErrors, setDefErrors] = useState<string[]>([]);
  const [previewData, setPreviewData] = useState<{ result: unknown[]; row_count: number } | null>(null);
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

  // sync defText from editing
  useEffect(() => {
    setDefText(JSON.stringify(editing?.definition ?? {}, null, 2));
    setDefValid(true);
    setDefErrors([]);
    setPreviewData(null); // Clear preview when editing changes
    setSensitivityInfo(null); // Clear sensitivity when editing changes
    
    // Analyze sensitivity for the current definition
    if (editing?.definition) {
      analyzeSensitivity(editing.definition);
    }
  }, [editing, analyzeSensitivity]);

  const handlePreviewExample = async (exampleId: string) => {
    setPreviewingExample(exampleId);
    try {
      const response = await previewExampleComputation(exampleId);
      setPreviewData({ result: response.result, row_count: response.row_count });
    } catch (error) {
      console.error('Error previewing example:', error);
      setPreviewData(null);
      toast.error(extractPreviewErrorMessage(error));
    } finally {
      setPreviewingExample(null);
    }
  };

  const datasetColumns = useMemo(() => {
    if (!editing?.dataset) return [] as { name: string; type: string }[];
    return schemas[editing.dataset] || [];
  }, [editing?.dataset, schemas]);

  return (
    <Modal show={show} onHide={onClose} size="xl" centered>
      <Modal.Header closeButton>
        <Modal.Title>
          {editing?.id ? (
            <>
              <FaEdit className="me-2 text-primary" />
              Edit Computation
            </>
          ) : (
            <>
              <FaPlus className="me-2 text-primary" />
              Create New Computation
            </>
          )}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body style={{ maxHeight: '85vh', overflowY: 'auto' }}>
        <Row className="g-4">
          {examples.length > 0 && (
            <Col md={12}>
              <Card className="border-info">
                <Card.Header className="bg-info text-white py-2">
                  <h6 className="mb-0">
                    <FaLightbulb className="me-2" />
                    Quick Start Examples
                  </h6>
                </Card.Header>
                <Card.Body className="py-3">
                  <p className="text-muted mb-3">
                    Load pre-built examples and customize them for your needs. Click the eye icon to preview results:
                  </p>
                  <div className="d-flex flex-wrap gap-2">
                    {examples.map((ex) => (
                      <div key={ex.id} className="d-flex gap-1">
                        <WithTooltip tip={`Load example: ${ex.title}`}>
                          <Button
                            size="sm"
                            variant="outline-primary"
                            onClick={() => {
                              setDefText(JSON.stringify(ex.definition, null, 2));
                              setDefValid(true);
                              setEditing((s) => ({ 
                                ...(s as ComputationDef), 
                                name: ex.title,
                                dataset: ex.dataset, 
                                definition: ex.definition,
                                description: ex.description || ''
                              }));
                              try {
                                const errs = validateDefinition(ex.definition, ex.dataset, schemas);
                                setDefErrors(errs);
                              } catch {
                                setDefErrors([]);
                              }
                            }}
                            className="fw-bold"
                          >
                            <FaFileAlt className="me-1" />
                            {ex.title}
                          </Button>
                        </WithTooltip>
                        <WithTooltip tip={`Preview example: ${ex.title}`}>
                          <Button
                            size="sm"
                            variant="outline-info"
                            disabled={previewingExample === ex.id}
                            onClick={() => handlePreviewExample(ex.id)}
                          >
                            {previewingExample === ex.id ? <Spinner animation="border" size="sm" /> : <FaEye />}
                          </Button>
                        </WithTooltip>
                      </div>
                    ))}
                  </div>
                  {previewData && (
                    <Card className="mt-3">
                      <Card.Header className="py-2 bg-success text-white">
                        <small className="fw-bold">
                          <FaChartBar className="me-1" />
                          Preview Results ({previewData.row_count} rows)
                        </small>
                      </Card.Header>
                      <Card.Body style={{ maxHeight: '200px', overflow: 'auto', fontSize: '13px' }}>
                        <pre className="mb-0 text-success">{JSON.stringify(previewData.result, null, 2)}</pre>
                      </Card.Body>
                    </Card>
                  )}
                </Card.Body>
              </Card>
            </Col>
          )}
          
          {/* Basic Information Section */}
          <Col md={12}>
            <Card className="border-primary">
              <Card.Header className="bg-primary text-white py-2">
                <h6 className="mb-0">
                  <FaInfoCircle className="me-2" />
                  Basic Information
                </h6>
              </Card.Header>
              <Card.Body className="py-3">
                <Row className="g-3">
                  <Col md={8}>
                    <Form.Group>
                      <Form.Label className="fw-bold">Computation Name</Form.Label>
                      <Form.Control
                        size="lg"
                        value={editing?.name ?? ''}
                        onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), name: e.target.value }))}
                        placeholder="Enter a descriptive name..."
                      />
                      <Form.Text className="text-muted">
                        Choose a clear name that explains what this computation does.
                      </Form.Text>
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label className="fw-bold">Dataset Source</Form.Label>
                      <Form.Select
                        size="lg"
                        value={editing?.dataset ?? 'gold'}
                        onChange={(e) => {
                          const newDs = e.target.value;
                          setEditing((s) => ({ ...(s as ComputationDef), dataset: newDs }));
                          try {
                            const errs = validateDefinition(editing?.definition ?? {}, newDs, schemas);
                            setDefErrors(errs);
                          } catch {
                            setDefErrors([]);
                          }
                        }}
                      >
                        {(sources.length ? sources : ['gold', 'silver', 'bronze', 'enriched', 'alerts', 'sensors']).map((s) => (
                          <option key={s} value={s}>
                            {s === 'gold' ? (
                              <>
                                <FaTrophy className="me-1" />
                                Gold (Clean)
                              </>
                            ) : s === 'silver' ? (
                              <>
                                <FaMedal className="me-1" />
                                Silver (Normalized)
                              </>
                            ) : s === 'bronze' ? (
                              <>
                                <FaAward className="me-1" />
                                Bronze (Raw)
                              </>
                            ) : s === 'enriched' ? (
                              <>
                                <FaStar className="me-1" />
                                Enriched
                              </>
                            ) : s === 'alerts' ? (
                              <>
                                <FaBell className="me-1" />
                                Alerts
                              </>
                            ) : s === 'sensors' ? (
                              <>
                                <FaBroadcastTower className="me-1" />
                                Sensors
                              </>
                            ) : s}
                          </option>
                        ))}
                      </Form.Select>
                      {datasetColumns.length > 0 && (
                        <div className="form-text" style={{ maxHeight: 120, overflow: 'auto' }}>
                          <strong>Available columns:</strong><br />
                          <div className="mt-1">
                            {datasetColumns.map((f, idx) => (
                              <Badge key={idx} bg="light" text="dark" className="me-1 mb-1">
                                {f.name} <span className="text-muted">({f.type})</span>
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </Form.Group>
                  </Col>
                </Row>
                
                <Row className="mt-3">
                  <Col md={12}>
                    <Form.Group>
                      <Form.Label className="fw-bold">Description</Form.Label>
                      <WithTooltip tip="Short description to explain what this computation does">
                        <Form.Control
                          size="lg"
                          value={editing?.description ?? ''}
                          onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), description: e.target.value }))}
                          placeholder="Describe what this computation analyzes or calculates..."
                        />
                      </WithTooltip>
                      <Form.Text className="text-muted">
                        Explain the purpose and expected output of this computation.
                      </Form.Text>
                    </Form.Group>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>

          {/* Definition Section */}
          <Col md={12}>
            <Card className="border-warning">
              <Card.Header className="bg-warning py-2">
                <h6 className="mb-0">
                  <FaCog className="me-2" />
                  Computation Definition
                </h6>
              </Card.Header>
              <Card.Body className="py-3">
                <Form.Group>
                  <Form.Label className="fw-bold d-flex justify-content-between align-items-center">
                    <span>JSON Definition</span>
                    <div className="d-flex gap-2">
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={() => {
                          try {
                            const formatted = JSON.stringify(JSON.parse(defText), null, 2);
                            setDefText(formatted);
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
                          const example = `{
  "select": ["*"],
  "where": {
    "column": "temperature",
    "operator": ">",
    "value": 25
  },
  "orderBy": [{"column": "timestamp", "direction": "DESC"}],
  "limit": 100
}`;
                          setDefText(example);
                          try {
                            const obj = JSON.parse(example);
                            setDefValid(true);
                            setEditing((s) => ({ ...(s as ComputationDef), definition: obj }));
                            const errs = validateDefinition(obj, editing?.dataset, schemas);
                            setDefErrors(errs);
                          } catch {
                            setDefErrors([]);
                          }
                        }}
                        title="Load example template"
                      >
                        <FaFileAlt className="me-1" />
                        Example
                      </Button>
                    </div>
                  </Form.Label>
                  <WithTooltip tip="Edit the JSON definition: select, where, orderBy, limit">
                    <Form.Control
                      as="textarea"
                      rows={20}
                      value={defText}
                      isInvalid={!defValid}
                      onChange={(e) => {
                        const text = e.target.value;
                        setDefText(text);
                        try {
                          const obj = JSON.parse(text);
                          setDefValid(true);
                          setEditing((s) => ({ ...(s as ComputationDef), definition: obj }));
                          const errs = validateDefinition(obj, editing?.dataset, schemas);
                          setDefErrors(errs);
                          // Analyze sensitivity when definition changes
                          analyzeSensitivity(obj);
                        } catch {
                          setDefValid(false);
                          setDefErrors([]);
                          setSensitivityInfo(null);
                        }
                      }}
                      style={{ 
                        fontFamily: 'Monaco, Menlo, "Ubuntu Mono", "Courier New", monospace',
                        fontSize: '13px',
                        lineHeight: '1.6',
                        resize: 'vertical',
                        minHeight: '300px',
                        maxHeight: '600px'
                      }}
                      placeholder={'{\n  "select": ["temperature", "humidity", "timestamp"],\n  "where": {\n    "column": "temperature",\n    "operator": ">",\n    "value": 25\n  },\n  "orderBy": [{"column": "timestamp", "direction": "DESC"}],\n  "limit": 100\n}'}
                    />
                  </WithTooltip>
                  <Form.Control.Feedback type="invalid">
                    <FaTimes className="me-1" />
                    Invalid JSON syntax. Please check your brackets, quotes, and commas.
                  </Form.Control.Feedback>
                  <div className="d-flex justify-content-between align-items-start mt-2">
                    <Form.Text className="text-muted">
                      Define your computation using JSON. Use <code>select</code>, <code>where</code>, <code>orderBy</code>, and <code>limit</code> clauses.
                      <br />
                      <strong><FaLightbulb className="me-1" />Tip:</strong> Use the Format button to clean up your JSON, or drag the bottom-right corner to resize the editor.
                    </Form.Text>
                    <div className="text-muted small">
                      Lines: {defText.split('\n').length} | 
                      Chars: {defText.length} |
                      <span className={defValid ? "text-success" : "text-danger"}>
                        {defValid ? " Valid JSON ✓" : " Invalid JSON ✗"}
                      </span>
                    </div>
                  </div>
                  {defErrors.length > 0 && defValid && (
                    <Alert variant="danger" className="mt-2 mb-0 py-2">
                      <div className="fw-bold small mb-1">
                        <FaTimes className="me-1" />
                        Definition Issues:
                      </div>
                      <ul className="mb-0 small">
                        {defErrors.map((er, idx) => (
                          <li key={idx}>{er}</li>
                        ))}
                      </ul>
                    </Alert>
                  )}
                </Form.Group>
              </Card.Body>
            </Card>
          </Col>

          {/* Sensitivity Analysis Section */}
          <Col md={12}>
            <Card className={`border-${sensitivityInfo?.sensitivity === 'restricted' ? 'danger' : sensitivityInfo?.sensitivity === 'confidential' ? 'warning' : sensitivityInfo?.sensitivity === 'internal' ? 'info' : 'secondary'}`}>
              <Card.Header className={`py-2 ${sensitivityInfo?.sensitivity === 'restricted' ? 'bg-danger text-white' : sensitivityInfo?.sensitivity === 'confidential' ? 'bg-warning' : sensitivityInfo?.sensitivity === 'internal' ? 'bg-info text-white' : 'bg-secondary text-white'}`}>
                <h6 className="mb-0">
                  <FaShieldAlt className="me-2" />
                  Data Sensitivity
                  {analyzingSensitivity && <Spinner animation="border" size="sm" className="ms-2" />}
                </h6>
              </Card.Header>
              <Card.Body className="py-3">
                {sensitivityInfo ? (
                  <>
                    <div className="d-flex align-items-center gap-2 mb-2">
                      <span className="fw-bold">Inherited Sensitivity:</span>
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
                  <div className="text-muted small">
                    {defValid ? 'Enter a valid definition to analyze data sensitivity.' : 'Fix JSON errors to analyze sensitivity.'}
                  </div>
                )}
              </Card.Body>
            </Card>
          </Col>

          {/* Settings Section */}
          <Col md={12}>
            <Card className="border-success">
              <Card.Header className="bg-success text-white py-2">
                <h6 className="mb-0">
                  <FaToggleOn className="me-2" />
                  Settings
                </h6>
              </Card.Header>
              <Card.Body className="py-3">
                <Form.Check
                  type="switch"
                  id="enabled"
                  label={
                    <span className="fw-bold">
                      {!!editing?.enabled ? '✅ Enabled' : '❌ Disabled'}
                    </span>
                  }
                  checked={!!editing?.enabled}
                  onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), enabled: e.target.checked }))}
                />
                <Form.Text className="text-muted">
                  {!!editing?.enabled 
                    ? "This computation will be available for execution and dashboard tiles." 
                    : "This computation will be saved but not available for execution."
                  }
                </Form.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Modal.Body>
      <Modal.Footer className="d-flex justify-content-between">
        <div>
          <WithTooltip tip="Discard changes and close">
            <Button variant="outline-secondary" onClick={onClose} size="lg">
              <FaTimes className="me-1" />
              Cancel
            </Button>
          </WithTooltip>
        </div>
        <div>
          <WithTooltip tip="Save computation">
            <Button
              variant="primary"
              onClick={onSave}
              disabled={!editing || !defValid || defErrors.length > 0 || !editing.name?.trim()}
              size="lg"
              className="fw-bold"
            >
              {editing?.id ? (
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
          </WithTooltip>
        </div>
      </Modal.Footer>
    </Modal>
  );
};

export default EditorModal;
