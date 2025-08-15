import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Form, Row, Spinner, Pagination, Breadcrumb } from 'react-bootstrap';
import {
  NormalizationRule,
  listNormalizationRules,
  createNormalizationRule,
  updateNormalizationRule,
  deleteNormalizationRule,
  fetchPartitions,
} from '../api/backendRequests';
import { useError } from '../context/ErrorContext';
import ThemedTable from '../components/ThemedTable';

const emptyForm = { ingestion_id: '', raw_key: '', canonical_key: '', enabled: true };

const NormalizationRulesPage: React.FC = () => {
  const { setError } = useError();
  const [rules, setRules] = useState<NormalizationRule[]>([]);
  const [partitions, setPartitions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<typeof emptyForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [errors, setErrors] = useState<{ ingestion_id?: string; raw_key?: string; canonical_key?: string }>({});
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortKey, setSortKey] = useState<'raw_key' | 'canonical_key' | 'enabled' | 'applied_count' | 'last_applied_at' | 'updated_at'>('raw_key');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

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

  const validateIngestionId = (value: string) => {
    const v = value.trim();
    if (!v) return 'Ingestion ID is required';
    return undefined;
  };

  const load = async () => {
    setLoading(true);
    try {
      const [rulesData, partitionsData] = await Promise.all([
        listNormalizationRules(),
        fetchPartitions()
      ]);
      setRules(rulesData);
      setPartitions(partitionsData);
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

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      const av = (a as any)[sortKey];
      const bv = (b as any)[sortKey];
      // Normalize undefined/null
      const A = av ?? '';
      const B = bv ?? '';
      if (typeof A === 'number' && typeof B === 'number') return (A - B) * dir;
      const as = String(A).toLowerCase();
      const bs = String(B).toLowerCase();
      if (as < bs) return -1 * dir;
      if (as > bs) return 1 * dir;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const startIdx = (currentPage - 1) * pageSize;
  const paged = useMemo(() => sorted.slice(startIdx, startIdx + pageSize), [sorted, startIdx, pageSize]);

  const setSort = (key: typeof sortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const formatDate = (d?: string | null) => (d ? new Date(d).toLocaleString() : '');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Validate
    const newErrors: { ingestion_id?: string; raw_key?: string; canonical_key?: string } = {};
    newErrors.ingestion_id = validateIngestionId(form.ingestion_id);
    if (!editingId) newErrors.raw_key = validateRawKey(form.raw_key);
    newErrors.canonical_key = validateCanonicalKey(form.canonical_key);
    setErrors(newErrors);
    if (newErrors.ingestion_id || newErrors.raw_key || newErrors.canonical_key) return;

    try {
      if (editingId) {
        const updated = await updateNormalizationRule(editingId, {
          ingestion_id: form.ingestion_id.trim(),
          canonical_key: form.canonical_key,
          enabled: form.enabled,
        });
        setRules((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
      } else {
        const created = await createNormalizationRule({
          ingestion_id: form.ingestion_id.trim(),
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
    setForm({ ingestion_id: rule.ingestion_id || '', raw_key: rule.raw_key, canonical_key: rule.canonical_key, enabled: rule.enabled });
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

  // Helper to check if form has validation errors
  const hasValidationErrors = () => {
    if (loading) return true;
    if (editingId) {
      return !!validateIngestionId(form.ingestion_id) || !!validateCanonicalKey(form.canonical_key);
    }
    return !!validateIngestionId(form.ingestion_id) || !!validateRawKey(form.raw_key) || !!validateCanonicalKey(form.canonical_key);
  };

  return (
    <div className="container pt-3 pb-4">
      <Row className="g-2 mb-2">
        <Col>
          <Breadcrumb className="mb-0">
            <Breadcrumb.Item active>Normalization</Breadcrumb.Item>
          </Breadcrumb>
        </Col>
      </Row>
      <Row className="g-3">
        <Col md={5}>
          <Card className="shadow-sm border-body">
            <Card.Header className="bg-body-tertiary">{editingId ? 'Edit Rule' : 'Add Rule'}</Card.Header>
            <Card.Body className="bg-body-tertiary">
              <Form onSubmit={onSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Ingestion ID</Form.Label>
                  <Form.Control
                    as="select"
                    value={form.ingestion_id}
                    isInvalid={!!errors.ingestion_id}
                    onChange={(e) => {
                      const val = e.target.value;
                      setForm((f) => ({ ...f, ingestion_id: val }));
                      if (errors.ingestion_id) setErrors((er) => ({ ...er, ingestion_id: undefined }));
                    }}
                    required
                  >
                    <option value="">Select Partition...</option>
                    {partitions.map((partition) => (
                      <option key={partition} value={partition}>
                        {partition}
                      </option>
                    ))}
                  </Form.Control>
                  <Form.Text className="text-body-secondary">
                    Select the data partition this rule applies to.
                  </Form.Text>
                  <Form.Control.Feedback type="invalid">{errors.ingestion_id}</Form.Control.Feedback>
                </Form.Group>
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
                  <Form.Text className="text-body-secondary">
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
                  <Form.Text className="text-body-secondary">
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
                    disabled={hasValidationErrors()}
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
          <Card className="shadow-sm border-body">
            <Card.Header className="bg-body-tertiary">
              <div className="d-flex flex-wrap gap-2 align-items-center justify-content-between">
                <div className="d-flex align-items-center gap-2">
                  <strong>Normalization Rules</strong>
                  <small className="text-body-secondary">({visibleCount} of {totalCount})</small>
                  {lastRefreshed && (
                    <small className="text-body-secondary">• Updated {lastRefreshed.toLocaleTimeString()}</small>
                  )}
                </div>
                <div className="d-flex align-items-center gap-2">
                  <Form.Select
                    size="sm"
                    style={{ minWidth: '5rem', maxWidth: '7rem' }}
                    value={pageSize}
                    onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                    aria-label="Rows per page"
                  >
                    <option value={10}>10 / page</option>
                    <option value={25}>25 / page</option>
                    <option value={50}>50 / page</option>
                  </Form.Select>
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
              <ThemedTable striped hover responsive>
                <thead>
                  <tr>
                    <th style={{ whiteSpace: 'nowrap' }}>ID</th>
                    <th>Ingestion ID</th>
                    <th role="button" onClick={() => setSort('raw_key')}>Raw Key {sortKey==='raw_key' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th role="button" onClick={() => setSort('canonical_key')}>Canonical Key {sortKey==='canonical_key' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th role="button" onClick={() => setSort('enabled')}>Enabled {sortKey==='enabled' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th role="button" onClick={() => setSort('applied_count')}>Applied {sortKey==='applied_count' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th role="button" onClick={() => setSort('last_applied_at')}>Last Applied {sortKey==='last_applied_at' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th role="button" onClick={() => setSort('updated_at')}>Updated {sortKey==='updated_at' ? (sortDir==='asc' ? '▲' : '▼') : ''}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((r) => (
                    <tr key={r.id} style={{ opacity: r.enabled ? 1 : 0.7 }}>
                      <td>{r.id}</td>
                      <td>{r.ingestion_id || 'N/A'}</td>
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
              </ThemedTable>
              <div className="d-flex justify-content-between align-items-center mt-2">
                <div className="text-body-secondary small">Showing {startIdx + 1}-{Math.min(startIdx + pageSize, sorted.length)} of {sorted.length}</div>
                <Pagination size="sm" className="mb-0">
                  <Pagination.Prev onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={currentPage === 1} />
                  <Pagination.Item active>{currentPage}</Pagination.Item>
                  <Pagination.Next onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} />
                </Pagination>
              </div>
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
