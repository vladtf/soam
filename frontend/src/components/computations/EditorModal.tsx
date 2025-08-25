import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Row, Col, Form, Alert, Button, Card, Spinner } from 'react-bootstrap';
import { toast } from 'react-toastify';
import WithTooltip from '../../components/WithTooltip';
import type { ComputationDef, ComputationExample } from '../../api/backendRequests';
import { previewExampleComputation } from '../../api/backendRequests';
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

  // sync defText from editing
  useEffect(() => {
    setDefText(JSON.stringify(editing?.definition ?? {}, null, 2));
    setDefValid(true);
    setDefErrors([]);
    setPreviewData(null); // Clear preview when editing changes
  }, [editing]);

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
    <Modal show={show} onHide={onClose} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>{editing?.id ? 'Edit Computation' : 'New Computation'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Row className="g-3">
          {examples.length > 0 && (
            <Col md={12}>
              <div className="mb-3">
                <span className="text-body-secondary small">Examples:</span>
                <div className="d-flex flex-wrap gap-2 mt-2">
                  {examples.map((ex) => (
                    <div key={ex.id} className="d-flex gap-1">
                      <WithTooltip tip={`Load example: ${ex.title}`}>
                        <Button
                          size="sm"
                          variant="outline-secondary"
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
                        >
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
                          {previewingExample === ex.id ? <Spinner animation="border" size="sm" /> : '👁️'}
                        </Button>
                      </WithTooltip>
                    </div>
                  ))}
                </div>
              </div>
              {previewData && (
                <Card className="mb-3">
                  <Card.Header className="py-2">
                    <small>Preview Results ({previewData.row_count} rows)</small>
                  </Card.Header>
                  <Card.Body style={{ maxHeight: '200px', overflow: 'auto', fontSize: '0.85rem' }}>
                    <pre className="mb-0">{JSON.stringify(previewData.result, null, 2)}</pre>
                  </Card.Body>
                </Card>
              )}
            </Col>
          )}
          <Col md={6}>
            <Form.Group>
              <Form.Label>Name</Form.Label>
              <Form.Control
                value={editing?.name ?? ''}
                onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), name: e.target.value }))}
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group>
              <Form.Label>Dataset</Form.Label>
              <Form.Select
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
                    {s}
                  </option>
                ))}
              </Form.Select>
              {datasetColumns.length > 0 && (
                <div className="form-text" style={{ maxHeight: 120, overflow: 'auto' }}>
                  <strong>Columns:</strong> {datasetColumns.map((f) => `${f.name} (${f.type})`).join(', ')}
                </div>
              )}
            </Form.Group>
          </Col>
          <Col md={12}>
            <Form.Group>
              <Form.Label>Description</Form.Label>
              <WithTooltip tip="Short description to explain what this computation does">
                <Form.Control
                value={editing?.description ?? ''}
                onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), description: e.target.value }))}
                />
              </WithTooltip>
            </Form.Group>
          </Col>
          <Col md={12}>
            <Form.Group>
              <Form.Label>Definition (JSON)</Form.Label>
              <WithTooltip tip="Edit the JSON definition: select, where, orderBy, limit">
                <Form.Control
                as="textarea"
                rows={10}
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
                  } catch {
                    setDefValid(false);
                    setDefErrors([]);
                  }
                }}
                />
              </WithTooltip>
              <Form.Control.Feedback type="invalid">Invalid JSON</Form.Control.Feedback>
              {defErrors.length > 0 && defValid && (
                <Alert variant="danger" className="mt-2 mb-0 py-2">
                  <div className="fw-bold small mb-1">Definition issues:</div>
                  <ul className="mb-0 small">
                    {defErrors.map((er, idx) => (
                      <li key={idx}>{er}</li>
                    ))}
                  </ul>
                </Alert>
              )}
            </Form.Group>
          </Col>
          <Col md={12}>
            <Form.Check
              type="switch"
              id="enabled"
              label="Enabled"
              checked={!!editing?.enabled}
              onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), enabled: e.target.checked }))}
            />
          </Col>
        </Row>
      </Modal.Body>
      <Modal.Footer>
        <WithTooltip tip="Discard changes and close">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </WithTooltip>
        <WithTooltip tip="Save computation">
          <Button
            onClick={onSave}
            disabled={!editing || !defValid || defErrors.length > 0 || !editing.name?.trim()}
          >
            Save
          </Button>
        </WithTooltip>
      </Modal.Footer>
    </Modal>
  );
};

export default EditorModal;
