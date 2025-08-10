import React, { useEffect, useState } from 'react';
import { Button, Card, Col, Form, Row, Table, Modal, Badge, Alert, Spinner } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import { useTheme } from '../context/ThemeContext';
import { ComputationDef, createComputation, deleteComputation, listComputations, previewComputation, updateComputation, fetchComputationExamples, ComputationExample, fetchComputationSchemas } from '../api/backendRequests';

const empty: ComputationDef = { name: '', dataset: 'silver', definition: {}, description: '', enabled: true };

const ComputationsPage: React.FC = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [items, setItems] = useState<ComputationDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<ComputationDef | null>(null);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewOpen, setPreviewOpen] = useState<boolean>(false);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [defText, setDefText] = useState<string>('{}');
  const [defValid, setDefValid] = useState<boolean>(true);
  const [sources, setSources] = useState<string[]>([]);
  const [examples, setExamples] = useState<ComputationExample[]>([]);
  const [dslOps, setDslOps] = useState<string[]>([]);
  const [schemas, setSchemas] = useState<Record<string, { name: string; type: string }[]>>({});
  const [defErrors, setDefErrors] = useState<string[]>([]);

  const getFieldType = (dataset: string | undefined, col: string): string | undefined => {
    if (!dataset || !schemas[dataset]) return undefined;
    const entry = schemas[dataset]?.find(f => f.name === col);
    return entry?.type;
  };

  const sparkTypeToCat = (t?: string): 'number' | 'string' | 'boolean' | 'other' => {
    const s = (t || '').toLowerCase();
    if (!s) return 'other';
    if (s === 'string' || s.startsWith('varchar') || s.startsWith('char')) return 'string';
    if (s === 'boolean') return 'boolean';
    if (
      s === 'byte' || s === 'short' || s === 'int' || s === 'integer' || s === 'long' ||
      s === 'float' || s === 'double' || s.startsWith('decimal')
    ) return 'number';
    return 'other';
  };

  const validateDefinition = (defObj: unknown, dataset: string | undefined) => {
    const errs: string[] = [];
    if (!defObj || typeof defObj !== 'object' || Array.isArray(defObj)) {
      errs.push('Definition must be a JSON object.');
      return errs;
    }
    const obj = defObj as Record<string, unknown>;

    // select
    if (Object.prototype.hasOwnProperty.call(obj, 'select')) {
      const sel = obj.select;
      if (!Array.isArray(sel)) errs.push('select must be an array of column names.');
      else (sel as unknown[]).forEach((c, i) => {
        if (typeof c !== 'string') errs.push(`select[${i}] must be a string.`);
        else if (dataset && schemas[dataset] && !getFieldType(dataset, c)) errs.push(`select column not found: ${c}`);
      });
    }

    // where
    if (Object.prototype.hasOwnProperty.call(obj, 'where')) {
      const where = obj.where;
      if (!Array.isArray(where)) errs.push('where must be an array of conditions.');
      else (where as unknown[]).forEach((w, i) => {
        if (!w || typeof w !== 'object' || Array.isArray(w)) { errs.push(`where[${i}] must be an object.`); return; }
        const wObj = w as Record<string, unknown>;
        const col = wObj.col;
        const op = wObj.op;
        const value = wObj.value as unknown;
        if (typeof col !== 'string') errs.push(`where[${i}].col must be a string.`);
        const t = typeof col === 'string' ? getFieldType(dataset, col) : undefined;
        if (dataset && schemas[dataset] && typeof col === 'string' && !t) errs.push(`where column not found: ${col}`);
        if (typeof op !== 'string') errs.push(`where[${i}].op must be a string.`);
        const typeCat = sparkTypeToCat(t);
        // operator compatibility
        const strOps = new Set(['==','!=','contains']);
        const numOps = new Set(['>','>=','<','<=','==','!=']);
        const boolOps = new Set(['==','!=']);
        if (typeof op === 'string') {
          if (typeCat === 'string' && !strOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for string`);
          if (typeCat === 'number' && !numOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for number`);
          if (typeCat === 'boolean' && !boolOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for boolean`);
        }
        // value type checks (soft)
        if (typeCat === 'number' && typeof value !== 'number') errs.push(`where[${i}].value should be a number for column ${col}`);
        if (typeCat === 'boolean' && typeof value !== 'boolean') errs.push(`where[${i}].value should be a boolean for column ${col}`);
        if (typeCat === 'string' && op === 'contains' && typeof value !== 'string') errs.push(`where[${i}].value should be a string for contains`);
      });
    }

    // orderBy
    if (Object.prototype.hasOwnProperty.call(obj, 'orderBy')) {
      const order = obj.orderBy;
      if (!Array.isArray(order)) errs.push('orderBy must be an array of { col, dir }');
      else (order as unknown[]).forEach((o, i) => {
        if (!o || typeof o !== 'object' || Array.isArray(o)) { errs.push(`orderBy[${i}] must be an object.`); return; }
        const oObj = o as Record<string, unknown>;
        const col = oObj.col;
        const dir = oObj.dir;
        if (typeof col !== 'string') errs.push(`orderBy[${i}].col must be a string.`);
        else if (dataset && schemas[dataset] && !getFieldType(dataset, col)) errs.push(`orderBy column not found: ${col}`);
        if (dir !== undefined) {
          if (typeof dir !== 'string' || !['asc','desc'].includes(dir.toLowerCase())) errs.push(`orderBy[${i}].dir must be 'asc' or 'desc'`);
        }
      });
    }

    // limit
    if (Object.prototype.hasOwnProperty.call(obj, 'limit')) {
      const lim = obj.limit;
      if (typeof lim !== 'number' || !Number.isInteger(lim) || lim <= 0) errs.push('limit must be a positive integer.');
    }
    return errs;
  };

  const load = async () => {
    setLoading(true);
    try {
      const data = await listComputations();
      setItems(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      // surface minimally; could wire into global error toast
      console.error('Failed to load computations:', message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { 
    load(); 
    // load examples/help
    (async () => {
      try {
        const info = await fetchComputationExamples();
        setSources(info.sources);
        setExamples(info.examples);
        setDslOps(info.dsl?.ops ?? []);
      } catch (e) {
        console.warn('Failed to fetch examples:', e);
      }
      try {
        const s = await fetchComputationSchemas();
        setSchemas(s.schemas || {});
      } catch (e) {
        console.warn('Failed to fetch schemas:', e);
      }
    })();
  }, []);

  const openNew = () => { 
    const base = { ...empty };
    setEditing(base); 
    setDefText(JSON.stringify(base.definition ?? {}, null, 2));
    setDefValid(true);
    setDefErrors([]);
    setShow(true); 
  };
  const openEdit = (it: ComputationDef) => { 
    setEditing({ ...it }); 
    setDefText(JSON.stringify(it.definition ?? {}, null, 2));
    setDefValid(true);
    // run validation using current schema
    try {
      const errs = validateDefinition(it.definition, it.dataset);
      setDefErrors(errs);
    } catch {
      setDefErrors([]);
    }
    setShow(true); 
  };
  const close = () => { setShow(false); setEditing(null); };

  const save = async () => {
    if (!editing) return;
    try {
      if (editing.id) await updateComputation(editing.id, editing);
      else await createComputation(editing);
      close();
      await load();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      alert(message);
    }
  };

  const doDelete = async (id?: number) => {
    if (!id) return;
    if (!window.confirm('Delete computation?')) return;
    await deleteComputation(id);
    await load();
  };

  const doPreview = async (id?: number) => {
    if (!id) return;
    setPreviewData(null);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const rows = await previewComputation(id);
      setPreviewData(rows ?? []);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      alert(message);
      setPreviewOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <div className="container pt-3 pb-4">
      <PageHeader title="Computations" right={<Button onClick={openNew}>New</Button>} />
      <Card className="shadow-sm border-body">
        <Card.Body>
          {sources.length > 0 && (
            <div className="mb-3 small text-body-secondary">
              <strong>Sources:</strong> {sources.join(', ')}
              {dslOps.length > 0 && <span className="ms-3"><strong>Ops:</strong> {dslOps.join(', ')}</span>}
            </div>
          )}
          {loading ? (
            <div>Loading…</div>
          ) : (
            <Table responsive hover size="sm" variant={isDark ? 'dark' : undefined}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Dataset</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id}>
                    <td>{it.name}</td>
                    <td><Badge bg="secondary">{it.dataset}</Badge></td>
                    <td>{it.enabled ? <Badge bg="success">enabled</Badge> : <Badge bg="secondary">disabled</Badge>}</td>
                    <td className="d-flex gap-2">
                      <Button size="sm" variant="outline-primary" onClick={() => openEdit(it)}>Edit</Button>
                      <Button size="sm" variant="outline-secondary" onClick={() => doPreview(it.id)}>Preview</Button>
                      <Button size="sm" variant="outline-danger" onClick={() => doDelete(it.id)}>Delete</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      <Modal show={show} onHide={close} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{editing?.id ? 'Edit Computation' : 'New Computation'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row className="g-3">
            {examples.length > 0 && (
              <Col md={12}>
                <div className="d-flex flex-wrap gap-2 align-items-center">
                  <span className="text-body-secondary small">Examples:</span>
                  {examples.map(ex => (
                    <Button key={ex.id} size="sm" variant="outline-secondary" onClick={() => {
                      setDefText(JSON.stringify(ex.definition, null, 2));
                      setDefValid(true);
                      setEditing(s => ({ ...(s as ComputationDef), dataset: ex.dataset, definition: ex.definition }));
                      // run immediate validation so issues are visible without edits
                      try {
                        const errs = validateDefinition(ex.definition, ex.dataset);
                        setDefErrors(errs);
                      } catch {
                        setDefErrors([]);
                      }
                    }}>{ex.title}</Button>
                  ))}
                </div>
              </Col>
            )}
            <Col md={6}>
              <Form.Group>
                <Form.Label>Name</Form.Label>
                <Form.Control value={editing?.name ?? ''} onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), name: e.target.value }))} />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Dataset</Form.Label>
                <Form.Select value={editing?.dataset ?? 'silver'} onChange={(e) => {
                  const newDs = e.target.value;
                  setEditing((s) => ({ ...(s as ComputationDef), dataset: newDs }));
                  // revalidate for new dataset
                  try {
                    const errs = validateDefinition((editing?.definition ?? {}), newDs);
                    setDefErrors(errs);
                  } catch {
                    setDefErrors([]);
                  }
                }}>
                  {(sources.length ? sources : ['silver','alerts','sensors']).map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </Form.Select>
                {editing?.dataset && schemas[editing.dataset] && schemas[editing.dataset]!.length > 0 && (
                  <div className="form-text" style={{ maxHeight: 120, overflow: 'auto' }}>
                    <strong>Columns:</strong> {schemas[editing.dataset]!.map(f => `${f.name} (${f.type})`).join(', ')}
                  </div>
                )}
              </Form.Group>
            </Col>
            <Col md={12}>
              <Form.Group>
                <Form.Label>Description</Form.Label>
                <Form.Control value={editing?.description ?? ''} onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), description: e.target.value }))} />
              </Form.Group>
            </Col>
            <Col md={12}>
              <Form.Group>
                <Form.Label>Definition (JSON)</Form.Label>
                <Form.Control as="textarea" rows={10}
                  value={defText}
                  isInvalid={!defValid}
                  onChange={(e) => {
                    const text = e.target.value;
                    setDefText(text);
                    try {
                      const obj = JSON.parse(text);
                      setDefValid(true);
                      setEditing((s) => ({ ...(s as ComputationDef), definition: obj }));
                      // semantic validation
                      const errs = validateDefinition(obj, editing?.dataset);
                      setDefErrors(errs);
                    } catch {
                      setDefValid(false);
                      setDefErrors([]);
                    }
                  }}
                />
                <Form.Control.Feedback type="invalid">Invalid JSON</Form.Control.Feedback>
                {defErrors.length > 0 && defValid && (
                  <Alert variant="danger" className="mt-2 mb-0 py-2">
                    <div className="fw-bold small mb-1">Definition issues:</div>
                    <ul className="mb-0 small">
                      {defErrors.map((er, idx) => (<li key={idx}>{er}</li>))}
                    </ul>
                  </Alert>
                )}
              </Form.Group>
            </Col>
            <Col md={12}>
              <Form.Check type="switch" id="enabled" label="Enabled" checked={!!editing?.enabled} onChange={(e) => setEditing((s) => ({ ...(s as ComputationDef), enabled: e.target.checked }))} />
            </Col>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={close}>Cancel</Button>
          <Button onClick={save} disabled={!editing || !defValid || defErrors.length > 0 || !editing.name?.trim()}>Save</Button>
        </Modal.Footer>
      </Modal>

      <Modal show={previewOpen} onHide={() => { setPreviewOpen(false); setPreviewData(null); }} size="lg">
        <Modal.Header closeButton><Modal.Title>Preview</Modal.Title></Modal.Header>
        <Modal.Body>
          {previewLoading ? (
            <div className="d-flex align-items-center gap-2">
              <Spinner animation="border" size="sm" />
              <span>Loading preview…</span>
            </div>
          ) : (
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(previewData, null, 2)}</pre>
          )}
        </Modal.Body>
      </Modal>
    </div>
  );
};

export default ComputationsPage;
