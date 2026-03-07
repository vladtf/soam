import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Row, Col, Form, Button, Badge, Alert,
  Card, Table, Spinner, Dropdown
} from 'react-bootstrap';
import {
  fetchQueryTemplates, executeOntologyQuery,
  QueryTemplate, QueryResult
} from '../api/buildingsApi';
import { extractErrorMessage } from '../utils/errorHandling';

const OntologyQueryEditor: React.FC = () => {
  const [query, setQuery] = useState('MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY count DESC');
  const [params, setParams] = useState<Record<string, string>>({});
  const [paramInputs, setParamInputs] = useState<string[]>([]);
  const [templates, setTemplates] = useState<QueryTemplate[]>([]);
  const [results, setResults] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchQueryTemplates()
      .then(setTemplates)
      .catch((e) => console.error('Failed to load templates:', e));
  }, []);

  const handleTemplateSelect = useCallback((template: QueryTemplate) => {
    setQuery(template.query);
    setParamInputs(template.params);
    setParams({});
    setResults(null);
    setError(null);
  }, []);

  const handleExecute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await executeOntologyQuery(query, params);
      setResults(result);
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [query, params]);

  const handleExportJSON = useCallback(() => {
    if (!results) return;
    const blob = new Blob([JSON.stringify(results.rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query-results.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const handleExportCSV = useCallback(() => {
    if (!results || results.rows.length === 0) return;
    const headers = Object.keys(results.rows[0]);
    const csv = [
      headers.join(','),
      ...results.rows.map(row =>
        headers.map(h => JSON.stringify(row[h] ?? '')).join(',')
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query-results.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleExecute();
    }
  }, [handleExecute]);

  return (
    <Container fluid className="py-3">
      <Row>
        {/* Template sidebar */}
        <Col md={3}>
          <Card>
            <Card.Header><strong>Query Templates</strong></Card.Header>
            <Card.Body className="p-0">
              {templates.map((t, i) => (
                <div
                  key={i}
                  className="p-2 border-bottom"
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleTemplateSelect(t)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleTemplateSelect(t)}
                >
                  <strong className="d-block">{t.name}</strong>
                  <small className="text-muted">{t.description}</small>
                </div>
              ))}
            </Card.Body>
          </Card>
        </Col>

        {/* Query editor + results */}
        <Col md={9}>
          <Card className="mb-3">
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span><strong>Cypher Query</strong></span>
              <Badge bg="info">Read-Only</Badge>
            </Card.Header>
            <Card.Body>
              <Form.Control
                as="textarea"
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="font-monospace mb-2"
                placeholder="Enter Cypher query... (Ctrl+Enter to execute)"
              />

              {/* Parameter inputs */}
              {paramInputs.length > 0 && (
                <Row className="mb-2">
                  {paramInputs.map((p) => (
                    <Col key={p} md={4}>
                      <Form.Group>
                        <Form.Label className="small">${p}</Form.Label>
                        <Form.Control
                          size="sm"
                          placeholder={`Value for $${p}`}
                          value={params[p] || ''}
                          onChange={(e) => setParams(prev => ({ ...prev, [p]: e.target.value }))}
                        />
                      </Form.Group>
                    </Col>
                  ))}
                </Row>
              )}

              <div className="d-flex gap-2">
                <Button onClick={handleExecute} disabled={loading || !query.trim()}>
                  {loading ? <Spinner size="sm" className="me-1" /> : null}
                  Execute
                </Button>
                {results && (
                  <Dropdown>
                    <Dropdown.Toggle variant="outline-secondary" size="sm">Export</Dropdown.Toggle>
                    <Dropdown.Menu>
                      <Dropdown.Item onClick={handleExportJSON}>JSON</Dropdown.Item>
                      <Dropdown.Item onClick={handleExportCSV}>CSV</Dropdown.Item>
                    </Dropdown.Menu>
                  </Dropdown>
                )}
              </div>
            </Card.Body>
          </Card>

          {error && <Alert variant="danger">{error}</Alert>}

          {/* Results table */}
          {results && results.rows.length > 0 && (
            <Card>
              <Card.Header>
                <strong>Results</strong>
                <Badge bg="secondary" className="ms-2">{results.count} rows</Badge>
              </Card.Header>
              <Card.Body className="p-0" style={{ maxHeight: '400px', overflow: 'auto' }}>
                <Table striped bordered hover size="sm" className="mb-0">
                  <thead className="sticky-top bg-light">
                    <tr>
                      {Object.keys(results.rows[0]).map((key) => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.rows.map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((val, j) => (
                          <td key={j}>
                            {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          )}

          {results && results.rows.length === 0 && (
            <Alert variant="info">Query returned no results.</Alert>
          )}
        </Col>
      </Row>
    </Container>
  );
};

export default OntologyQueryEditor;
