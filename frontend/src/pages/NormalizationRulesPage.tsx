import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Form, Row, Table, Spinner } from 'react-bootstrap';
import {
  NormalizationRule,
  listNormalizationRules,
  createNormalizationRule,
  updateNormalizationRule,
  deleteNormalizationRule,
} from '../api/backendRequests';
import { useError } from '../context/ErrorContext';

const emptyForm = { raw_key: '', canonical_key: '', enabled: true };

const NormalizationRulesPage: React.FC = () => {
  const { setError } = useError();
  const [rules, setRules] = useState<NormalizationRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<typeof emptyForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [errors, setErrors] = useState<{ raw_key?: string; canonical_key?: string }>({});
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Validation rules
  const RAW_KEY_MAX = 128;
  const CANON_KEY_MAX = 64;
  const rawKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]*$/; // allow dot, dash, underscore
  const canonicalPattern = /^[A-Za-z][A-Za-z0-9_]*$/; // snake/camel allowed, no hyphen/dot/space

  const hasDuplicateRawKey = (value: string, ignoreId?: number | null) => {
    const v = value.trim().toLowerCase();
    return rules.some((r) => r.raw_key.toLowerCase() === v && r.id !== (ignoreId ?? -1));
  };

  const validateRawKey = (value: string) => {
    const v = value.trim();
    if (!v) return 'Raw key is required';
    if (v.length > RAW_KEY_MAX) return `Max ${RAW_KEY_MAX} characters`;
    if (!rawKeyPattern.test(v)) return 'Use letters, numbers, dot, dash or underscore';
    if (hasDuplicateRawKey(v, editingId)) return 'A rule with this raw key already exists';
    return undefined;
  };

  const validateCanonicalKey = (value: string) => {
    const v = value.trim();
    if (!v) return 'Canonical key is required';
    if (v.length > CANON_KEY_MAX) return `Max ${CANON_KEY_MAX} characters`;
    if (!canonicalPattern.test(v)) return 'Start with a letter. Use only letters, numbers, underscore';
    return undefined;
  };

  const load = async () => {
    setLoading(true);
    try {
      const data = await listNormalizationRules();
      setRules(data);
  setLastRefreshed(new Date());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!filter) return rules;
    const f = filter.toLowerCase();
    return rules.filter((r) =>
      r.raw_key.toLowerCase().includes(f) || r.canonical_key.toLowerCase().includes(f)
    );
  }, [rules, filter]);

  const totalCount = rules.length;
  const visibleCount = filtered.length;

  const formatDate = (d?: string | null) => (d ? new Date(d).toLocaleString() : '');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
  // Validate
  const newErrors: { raw_key?: string; canonical_key?: string } = {};
  if (!editingId) newErrors.raw_key = validateRawKey(form.raw_key);
  newErrors.canonical_key = validateCanonicalKey(form.canonical_key);
  setErrors(newErrors);
  if (newErrors.raw_key || newErrors.canonical_key) return;

  try {
      if (editingId) {
        const updated = await updateNormalizationRule(editingId, {
          canonical_key: form.canonical_key,
          enabled: form.enabled,
        });
        setRules((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
      } else {
        const created = await createNormalizationRule({
      raw_key: form.raw_key.trim().toLowerCase(),
          canonical_key: form.canonical_key,
          enabled: form.enabled,
        });
        setRules((rs) => [created, ...rs]);
      }
      setForm(emptyForm);
      setEditingId(null);
    setErrors({});
    } catch (e) {
      setError(e);
    }
  };

  const onEdit = (rule: NormalizationRule) => {
    setEditingId(rule.id);
    setForm({ raw_key: rule.raw_key, canonical_key: rule.canonical_key, enabled: rule.enabled });
  };

  const onDelete = async (id: number) => {
    if (!confirm('Delete this rule?')) return;
    try {
      await deleteNormalizationRule(id);
      setRules((rs) => rs.filter((r) => r.id !== id));
    } catch (e) {
      setError(e);
    }
  };

  const onCancel = () => {
    setEditingId(null);
    setForm(emptyForm);
    setErrors({});
  };

  return (
    <div className="container mt-4">
      <Row>
        <Col md={5}>
          <Card>
            <Card.Header>{editingId ? 'Edit Rule' : 'Add Rule'}</Card.Header>
            <Card.Body>
              <Form onSubmit={onSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Raw Key</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., temp or Temperature"
                    value={form.raw_key}
                    disabled={!!editingId}
                    isInvalid={!!errors.raw_key}
                    onChange={(e) => {
                      const val = e.target.value;
                      setForm((f) => ({ ...f, raw_key: val }));
                      if (errors.raw_key) setErrors((er) => ({ ...er, raw_key: undefined }));
                    }}
                    onBlur={(e) => {
                      const cleaned = e.target.value.trim().toLowerCase();
                      setForm((f) => ({ ...f, raw_key: cleaned }));
                      setErrors((er) => ({ ...er, raw_key: validateRawKey(cleaned) }));
                    }}
                    required
                  />
                  <Form.Text className="text-muted">
                    Original column name from incoming data. Lowercased automatically on backend.
                  </Form.Text>
                  <Form.Control.Feedback type="invalid">{errors.raw_key}</Form.Control.Feedback>
                </Form.Group>
                <Form.Group className="mb-3">
                  <Form.Label>Canonical Key</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., temperature"
                    value={form.canonical_key}
                    isInvalid={!!errors.canonical_key}
                    onChange={(e) => {
                      const val = e.target.value;
                      setForm((f) => ({ ...f, canonical_key: val }));
                      if (errors.canonical_key) setErrors((er) => ({ ...er, canonical_key: undefined }));
                    }}
                    onBlur={(e) => {
                      const cleaned = e.target.value.trim().replace(/\s+/g, '_');
                      setForm((f) => ({ ...f, canonical_key: cleaned }));
                      setErrors((er) => ({ ...er, canonical_key: validateCanonicalKey(cleaned) }));
                    }}
                    required
                  />
                  <Form.Text className="text-muted">
                    Start with a letter. Use only letters, numbers, and underscore. Max {CANON_KEY_MAX} chars.
                  </Form.Text>
                  <Form.Control.Feedback type="invalid">{errors.canonical_key}</Form.Control.Feedback>
                </Form.Group>
                <Form.Group className="mb-3" controlId="enabled">
                  <Form.Check
                    type="switch"
                    label="Enabled"
                    checked={form.enabled}
                    onChange={(e) => setForm((f) => ({ ...f, enabled: e.currentTarget.checked }))}
                  />
                </Form.Group>
                <div className="d-flex gap-2">
                  <Button
                    type="submit"
                    disabled={
                      loading || (editingId ? Boolean(validateCanonicalKey(form.canonical_key)) : Boolean(validateRawKey(form.raw_key) || validateCanonicalKey(form.canonical_key)))
                    }
                  >
                    {editingId ? 'Save' : 'Create'}
                  </Button>
                  {editingId && (
                    <Button variant="secondary" onClick={onCancel}>
                      Cancel
                    </Button>
                  )}
                </div>
              </Form>
            </Card.Body>
          </Card>
        </Col>
        <Col md={7}>
          <Card>
            <Card.Header>
              <div className="d-flex flex-wrap gap-2 align-items-center justify-content-between">
                <div className="d-flex align-items-center gap-2">
                  <strong>Normalization Rules</strong>
                  <small className="text-muted">({visibleCount} of {totalCount})</small>
                  {lastRefreshed && (
                    <small className="text-muted">• Updated {lastRefreshed.toLocaleTimeString()}</small>
                  )}
                </div>
                <div className="d-flex align-items-center gap-2">
                  <Form.Control
                    size="sm"
                    style={{ maxWidth: 260 }}
                    placeholder="Filter..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  />
                  {filter && (
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      onClick={() => setFilter('')}
                      disabled={loading}
                    >
                      Clear
                    </Button>
                  )}
                  <Button size="sm" variant="outline-primary" onClick={load} disabled={loading}>
                    {loading ? (
                      <>
                        <Spinner animation="border" size="sm" className="me-1" /> Refreshing
                      </>
                    ) : (
                      'Refresh'
                    )}
                  </Button>
                </div>
              </div>
            </Card.Header>
            <Card.Body>
              <Table striped hover responsive>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Raw Key</th>
                    <th>Canonical Key</th>
                    <th>Enabled</th>
                    <th>Applied</th>
                    <th>Last Applied</th>
                    <th>Updated</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.id} style={{ opacity: r.enabled ? 1 : 0.7 }}>
                      <td>{r.id}</td>
                      <td>{r.raw_key}</td>
                      <td>{r.canonical_key}</td>
                      <td>
                        <Form.Check
                          type="switch"
                          checked={r.enabled}
                          onChange={async (e) => {
                            try {
                              const updated = await updateNormalizationRule(r.id, { enabled: e.currentTarget.checked });
                              setRules((rs) => rs.map((x) => (x.id === r.id ? updated : x)));
                            } catch (err) {
                              setError(err);
                            }
                          }}
                        />
                      </td>
                      <td>
                        <span className="badge bg-info text-dark">{r.applied_count ?? 0}</span>
                      </td>
                      <td>{formatDate(r.last_applied_at)}</td>
                      <td>{formatDate(r.updated_at || r.created_at)}</td>
                      <td className="text-end">
                        <Button size="sm" variant="outline-primary" className="me-2" onClick={() => onEdit(r)}>
                          Edit
                        </Button>
                        <Button size="sm" variant="outline-danger" onClick={() => onDelete(r.id)}>
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              {loading && <div>Loading...</div>}
              {!loading && filtered.length === 0 && <div>No rules found.</div>}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default NormalizationRulesPage;
