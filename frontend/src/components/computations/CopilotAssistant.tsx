import React, { useState } from 'react';
import { Modal, Form, Button, Card, Badge, Spinner, Alert } from 'react-bootstrap';
import { toast } from 'react-toastify';
import { generateComputationWithCopilot, ComputationRequest, ComputationSuggestion } from '../../api/backendRequests';
import { extractComputationErrorMessage } from '../../utils/errorHandling';

interface CopilotAssistantProps {
  show: boolean;
  onHide: () => void;
  onAcceptSuggestion: (suggestion: ComputationSuggestion) => void;
}

const CopilotAssistant: React.FC<CopilotAssistantProps> = ({ show, onHide, onAcceptSuggestion }) => {
  const [prompt, setPrompt] = useState('');
  const [preferredDataset, setPreferredDataset] = useState('');
  const [context, setContext] = useState('');
  const [suggestion, setSuggestion] = useState<ComputationSuggestion | null>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast.error('Please enter a description of what you want to compute');
      return;
    }

    setLoading(true);
    try {
      const request: ComputationRequest = {
        user_prompt: prompt,
        context: context.trim() || undefined,
        preferred_dataset: preferredDataset || undefined
      };

      const result = await generateComputationWithCopilot(request);
      setSuggestion(result);
      toast.success('Computation generated successfully!');
    } catch (error) {
      toast.error(extractComputationErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = () => {
    if (suggestion) {
      onAcceptSuggestion(suggestion);
      onHide();
      toast.success('Computation loaded from Copilot suggestion');
    }
  };

  const handleClose = () => {
    setSuggestion(null);
    setPrompt('');
    setPreferredDataset('');
    setContext('');
    onHide();
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'danger';
  };

  return (
    <Modal show={show} onHide={handleClose} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>🤖 Copilot - Generate Computation</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {!suggestion ? (
          <>
            <Alert variant="info" className="mb-3">
              <small>
                <strong>💡 Tip:</strong> Describe what you want to analyze in natural language. 
                Examples: "Show me the average temperature by sensor location" or "Find sensors with readings above normal"
              </small>
            </Alert>

            <Form>
              <Form.Group className="mb-3">
                <Form.Label>What do you want to compute? *</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g., 'Show me the average temperature by sensor location for the last week' or 'Find all sensors that reported values above normal thresholds'"
                  disabled={loading}
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Preferred Dataset (optional)</Form.Label>
                <Form.Select 
                  value={preferredDataset} 
                  onChange={(e) => setPreferredDataset(e.target.value)}
                  disabled={loading}
                >
                  <option value="">Any dataset</option>
                  <option value="bronze">Bronze (raw data)</option>
                  <option value="silver">Silver (cleaned data)</option>
                  <option value="enriched">Enriched (normalized data)</option>
                  <option value="gold">Gold (aggregated data)</option>
                  <option value="alerts">Alerts</option>
                </Form.Select>
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Additional Context (optional)</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={2}
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder="Any additional information about your use case or requirements"
                  disabled={loading}
                />
              </Form.Group>
            </Form>

            <div className="d-flex justify-content-end gap-2">
              <Button variant="secondary" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleGenerate} disabled={loading || !prompt.trim()}>
                {loading ? (
                  <>
                    <Spinner as="span" animation="border" size="sm" className="me-2" />
                    Generating...
                  </>
                ) : (
                  'Generate with Copilot 🤖'
                )}
              </Button>
            </div>
          </>
        ) : (
          <div>
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="mb-0">{suggestion.title}</h5>
              <Badge bg={getConfidenceColor(suggestion.confidence)}>
                {Math.round(suggestion.confidence * 100)}% confidence
              </Badge>
            </div>

            <p className="text-muted">{suggestion.description}</p>

            <Card className="mb-3">
              <Card.Header>
                <strong>Dataset:</strong> {suggestion.dataset}
              </Card.Header>
              <Card.Body>
                <pre className="mb-0" style={{ fontSize: '0.9em', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(suggestion.definition, null, 2)}
                </pre>
              </Card.Body>
            </Card>

            <Alert variant="info">
              <strong>Explanation:</strong><br />
              {suggestion.explanation.split('\n').map((line, idx) => (
                <div key={idx}>{line}</div>
              ))}
            </Alert>

            {suggestion.suggested_columns.length > 0 && (
              <div className="mb-3">
                <strong>Suggested Display Columns:</strong>
                <div className="mt-2">
                  {suggestion.suggested_columns.map((col, idx) => (
                    <Badge key={idx} bg="secondary" className="me-2">
                      {col}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="d-flex justify-content-between">
              <Button variant="outline-secondary" onClick={() => setSuggestion(null)}>
                ← Generate Another
              </Button>
              <div>
                <Button variant="secondary" onClick={handleClose} className="me-2">
                  Close
                </Button>
                <Button variant="success" onClick={handleAccept}>
                  Use This Computation ✓
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal.Body>
    </Modal>
  );
};

export default CopilotAssistant;
