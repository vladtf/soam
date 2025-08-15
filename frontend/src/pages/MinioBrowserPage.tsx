import React, { useEffect, useMemo, useState } from 'react';
import { Container, Row, Col, ListGroup, Button, Breadcrumb, Spinner, Form, Card, InputGroup, Alert, Badge, OverlayTrigger, Tooltip } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import { minioList, minioPreviewParquet, MinioListResponse, ParquetPreview, minioDeleteObjects, minioDeletePrefix } from '../api/backendRequests';
import { FaFolder, FaFileAlt, FaSync, FaLevelUpAlt, FaHome, FaSearch, FaEye, FaCopy } from 'react-icons/fa';
import ThemedReactJson from '../components/ThemedReactJson';

const MinioBrowserPage: React.FC = () => {
  const [prefix, setPrefix] = useState<string>('');
  const [listing, setListing] = useState<MinioListResponse>({ prefixes: [], files: [] });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<ParquetPreview | null>(null);
  const [limit, setLimit] = useState<number>(50);
  const [filter, setFilter] = useState<string>('');
  const [onlyParquet, setOnlyParquet] = useState<boolean>(true);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [foldersPage, setFoldersPage] = useState<number>(1);
  const [filesPage, setFilesPage] = useState<number>(1);
  const [foldersPageSize, setFoldersPageSize] = useState<number>(10);
  const [filesPageSize, setFilesPageSize] = useState<number>(10);

  const load = async (p: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await minioList(p);
      setListing(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(prefix);
  }, [prefix]);

  const goTo = (p: string) => {
    setPreviewKey(null);
    setPreview(null);
    setPrefix(p);
  setSelected({});
  };

  const enterPrefix = (folder: string) => {
    const newPrefix = folder;
    goTo(newPrefix);
  };

  const upOne = () => {
    if (!prefix) return;
    const parts = prefix.split('/').filter(Boolean);
    parts.pop();
    const up = parts.length ? parts.join('/') + '/' : '';
    goTo(up);
  };

  const previewParquet = async (key: string) => {
    setPreviewKey(key);
    setPreview(null);
    setLoading(true);
    setError(null);
    try {
      const res = await minioPreviewParquet(key, limit);
      setPreview(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (key: string, checked: boolean) => {
    setSelected((prev) => ({ ...prev, [key]: checked }));
  };

  const toggleSelectAll = (checked: boolean) => {
    const next: Record<string, boolean> = {};
    if (checked) filteredFiles.forEach((k) => (next[k] = true));
    setSelected(next);
  };

  const deleteSelected = async () => {
    const keys = Object.keys(selected).filter((k) => selected[k]);
    if (keys.length === 0) return;
    if (!confirm(`Delete ${keys.length} selected file(s)?`)) return;
    setLoading(true);
    setError(null);
    try {
      await minioDeleteObjects(keys);
      await load(prefix);
      setSelected({});
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const deleteAllInFolder = async () => {
    if (!prefix) return;
    if (!confirm(`Delete ALL objects under '${prefix}'?`)) return;
    setLoading(true);
    setError(null);
    try {
      await minioDeletePrefix(prefix);
      await load(prefix);
      setSelected({});
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Derived breadcrumb parts and filtered lists
  const breadcrumbParts = useMemo(() => {
    const parts = prefix.split('/').filter(Boolean);
    const acc: { label: string; path: string }[] = [];
    let cur = '';
    for (const p of parts) {
      cur += p + '/';
      acc.push({ label: p, path: cur });
    }
    return acc;
  }, [prefix]);

  const filteredFolders = useMemo(() => {
    const q = filter.toLowerCase();
    return listing.prefixes.filter((p) => {
      const name = p.split('/').filter(Boolean).pop() || p;
      return name.toLowerCase().includes(q);
    });
  }, [listing.prefixes, filter]);

  const filteredFiles = useMemo(() => {
    const q = filter.toLowerCase();
    return listing.files.filter((f) => {
      const name = f.split('/').pop() || f;
      const parquetOk = !onlyParquet || name.toLowerCase().endsWith('.parquet');
      return parquetOk && name.toLowerCase().includes(q);
    });
  }, [listing.files, filter, onlyParquet]);

  const allSelected = useMemo(() => {
    const keys = filteredFiles;
    if (keys.length === 0) return false;
    return keys.every((k) => selected[k]);
  }, [filteredFiles, selected]);

  // Pagination calculations and effects
  const foldersPages = Math.max(1, Math.ceil(filteredFolders.length / Math.max(1, foldersPageSize)));
  const filesPages = Math.max(1, Math.ceil(filteredFiles.length / Math.max(1, filesPageSize)));

  useEffect(() => {
    setFoldersPage(1);
  }, [filter, listing.prefixes, foldersPageSize]);

  useEffect(() => {
    setFilesPage(1);
  }, [filter, listing.files, filesPageSize, onlyParquet]);

  useEffect(() => {
    if (foldersPage > foldersPages) setFoldersPage(foldersPages);
  }, [foldersPages]);

  useEffect(() => {
    if (filesPage > filesPages) setFilesPage(filesPages);
  }, [filesPages]);

  const visibleFolders = useMemo(() => {
    const start = (foldersPage - 1) * foldersPageSize;
    return filteredFolders.slice(start, start + foldersPageSize);
  }, [filteredFolders, foldersPage, foldersPageSize]);

  const visibleFiles = useMemo(() => {
    const start = (filesPage - 1) * filesPageSize;
    return filteredFiles.slice(start, start + filesPageSize);
  }, [filteredFiles, filesPage, filesPageSize]);

  const refresh = () => load(prefix);

  return (
    <Container className="pt-3 pb-4">
      <PageHeader
        title="MinIO Browser"
        right={
          <div className="d-flex gap-2">
            <Button variant="outline-secondary" onClick={upOne} disabled={!prefix} title="Up one level">
              <FaLevelUpAlt className="me-1" /> Up
            </Button>
            <Button variant="outline-primary" onClick={refresh} title="Refresh">
              <FaSync className="me-1" /> Refresh
            </Button>
            <Button variant="outline-danger" onClick={deleteSelected} disabled={Object.keys(selected).filter((k)=>selected[k]).length===0} title="Delete selected files">
              Delete selected
            </Button>
            <Button variant="danger" onClick={deleteAllInFolder} disabled={!prefix} title="Delete all files in this folder">
              Delete ALL in folder
            </Button>
          </div>
        }
      />

      <Row className="g-2 mb-3">
        <Col>
          <Breadcrumb>
            <Breadcrumb.Item onClick={() => goTo('')} role="button" aria-label="Root" title="Root">
              <FaHome className="me-1" /> /
            </Breadcrumb.Item>
            {breadcrumbParts.map((b, i) => (
              <Breadcrumb.Item key={b.path} active={i === breadcrumbParts.length - 1} onClick={() => goTo(b.path)} role="button">
                {b.label}
              </Breadcrumb.Item>
            ))}
          </Breadcrumb>
        </Col>
      </Row>

      {error && (
        <Row className="g-2 mb-3">
          <Col>
            <Alert variant="danger" className="mb-0">
              {error}
            </Alert>
          </Col>
        </Row>
      )}

      <Row className="g-3">
        <Col md={4}>
          <Card className="shadow-sm border-body">
            <Card.Header className="d-flex align-items-center justify-content-between">
              <div>Browse</div>
              {loading && (
                <span role="status" aria-live="polite" className="d-inline-flex align-items-center">
                  <Spinner animation="border" size="sm" aria-hidden="true" />
                  <span className="visually-hidden ms-1">Loading...</span>
                </span>
              )}
            </Card.Header>
            <Card.Body>
              <InputGroup className="mb-2">
                <InputGroup.Text><FaSearch /></InputGroup.Text>
                <Form.Control
                  placeholder="Filter folders and files"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
              </InputGroup>
              <Form.Check
                type="checkbox"
                id="onlyParquet"
                label="Only .parquet files"
                checked={onlyParquet}
                onChange={(e) => setOnlyParquet(e.target.checked)}
                className="mb-3"
              />

              <div className="mb-2 fw-semibold d-flex align-items-center justify-content-between">
                <span>Folders</span>
                <InputGroup size="sm" style={{ width: 320 }}>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFoldersPage((p) => Math.max(1, p - 1))} disabled={foldersPage <= 1}>Prev</Button>
                  <InputGroup.Text>Page {foldersPage}/{foldersPages}</InputGroup.Text>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFoldersPage((p) => Math.min(foldersPages, p + 1))} disabled={foldersPage >= foldersPages}>Next</Button>
                  <InputGroup.Text>Per page</InputGroup.Text>
                  <Form.Select size="sm" value={foldersPageSize} onChange={(e) => setFoldersPageSize(Number(e.target.value))} style={{ maxWidth: 90 }}>
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </Form.Select>
                </InputGroup>
              </div>
              <ListGroup variant="flush" className="mb-3">
                {visibleFolders.length === 0 && (
                  <ListGroup.Item className="text-body-secondary">No folders</ListGroup.Item>
                )}
                {visibleFolders.map((p) => {
                  const name = (p.split('/').filter(Boolean).pop() || p) + '/';
                  return (
                    <ListGroup.Item action key={p} onClick={() => enterPrefix(p)} className="d-flex align-items-center">
                      <FaFolder className="me-2 text-warning" />
                      <OverlayTrigger placement="top" overlay={<Tooltip>{name}</Tooltip>}>
                        <span className="flex-grow-1 text-truncate" style={{ minWidth: 0, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>{name}</span>
                      </OverlayTrigger>
                    </ListGroup.Item>
                  );
                })}
              </ListGroup>

              <div className="mb-2 fw-semibold d-flex align-items-center justify-content-between">
                <div className="d-flex align-items-center gap-3">
                  <span>Files</span>
                  <Form.Check
                    type="checkbox"
                    id="selectAll"
                    label="Select all"
                    checked={allSelected}
                    onChange={(e) => toggleSelectAll(e.target.checked)}
                  />
                </div>
                <InputGroup size="sm" style={{ width: 360 }}>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFilesPage((p) => Math.max(1, p - 1))} disabled={filesPage <= 1}>Prev</Button>
                  <InputGroup.Text>Page {filesPage}/{filesPages}</InputGroup.Text>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFilesPage((p) => Math.min(filesPages, p + 1))} disabled={filesPage >= filesPages}>Next</Button>
                  <InputGroup.Text>Per page</InputGroup.Text>
                  <Form.Select size="sm" value={filesPageSize} onChange={(e) => setFilesPageSize(Number(e.target.value))} style={{ maxWidth: 90 }}>
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </Form.Select>
                </InputGroup>
              </div>
              <ListGroup variant="flush">
                {visibleFiles.length === 0 && (
                  <ListGroup.Item className="text-body-secondary">No files</ListGroup.Item>
                )}
                {visibleFiles.map((f) => {
                  const name = f.split('/').pop() || f;
                  const isParquet = name.toLowerCase().endsWith('.parquet');
                  const isPreviewedFile = previewKey === f;
                  return (
                    <ListGroup.Item 
                      action 
                      key={f} 
                      className={`d-flex align-items-center justify-content-between ${isPreviewedFile ? 'bg-primary-subtle border-primary' : ''}`}
                    >
                      <div className="d-flex align-items-center flex-grow-1" style={{ minWidth: 0 }} onClick={() => previewParquet(f)}>
                        <Form.Check className="me-2" checked={!!selected[f]} onChange={(e)=> toggleSelect(f, e.target.checked)} onClick={(e)=> e.stopPropagation()} />
                        <FaFileAlt className="me-2" />
                        <OverlayTrigger placement="top" overlay={<Tooltip>{name}</Tooltip>}>
                          <span className="text-truncate" style={{ minWidth: 0, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>{name}</span>
                        </OverlayTrigger>
                        {isParquet && <Badge bg="secondary" className="ms-2">parquet</Badge>}
                      </div>
                      <Button size="sm" variant="outline-secondary" aria-label={`Preview ${name}`} onClick={(e) => { e.stopPropagation(); previewParquet(f); }}>
                        <FaEye className="me-1" /> Preview
                      </Button>
                    </ListGroup.Item>
                  );
                })}
              </ListGroup>
            </Card.Body>
          </Card>
        </Col>
        <Col md={8}>
          <Card className="shadow-sm border-body">
            <Card.Header className="d-flex align-items-center justify-content-between">
              <div>
                Preview {previewKey && (
                  <span className="align-middle ms-2 d-inline-flex align-items-center" style={{ maxWidth: 480 }}>
                    <OverlayTrigger placement="top" overlay={<Tooltip>{previewKey}</Tooltip>}>
                      <Badge bg="light" text="dark" className="text-truncate" style={{ maxWidth: 420, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>{previewKey}</Badge>
                    </OverlayTrigger>
                    <OverlayTrigger placement="top" overlay={<Tooltip>Copy object key</Tooltip>}>
                      <Button size="sm" variant="outline-secondary" className="ms-2" aria-label="Copy object key" onClick={() => { if (previewKey) navigator.clipboard?.writeText(previewKey); }}>
                        <FaCopy />
                      </Button>
                    </OverlayTrigger>
                  </span>
                )}
              </div>
              <div className="d-flex align-items-center gap-2">
                <InputGroup size="sm" style={{ width: 140 }}>
                  <InputGroup.Text id="rows-label">Rows</InputGroup.Text>
                  <Form.Control
                    size="sm"
                    type="number"
                    min={1}
                    max={500}
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    aria-labelledby="rows-label"
                    aria-label="Rows to preview"
                  />
                </InputGroup>
                <Button size="sm" variant="outline-primary" disabled={!previewKey} onClick={() => { if (previewKey) previewParquet(previewKey); }} aria-label="Reload preview" title="Reload preview">
                  <FaSync className="me-1" /> Reload
                </Button>
              </div>
            </Card.Header>
            <Card.Body>
              {loading && previewKey && (
                <span role="status" aria-live="polite" className="d-inline-flex align-items-center">
                  <Spinner animation="border" aria-hidden="true" />
                  <span className="visually-hidden ms-2">Loading preview…</span>
                </span>
              )}
              {!previewKey && (
                <div className="text-body-secondary">Select a Parquet file to preview.</div>
              )}
              {preview && (
                <div style={{ maxHeight: 800, overflowY: 'auto' }}>
                  <div className="mb-3">
                    <h6 className="mb-2">Schema:</h6>
                    <ThemedReactJson 
                      src={preview.schema} 
                      collapsed={false}
                      name="schema"
                    />
                  </div>
                  <div>
                    <h6 className="mb-2">Data ({preview.rows.length} rows):</h6>
                    <div style={{ maxHeight: 650, overflowY: 'auto' }}>
                      <ThemedReactJson 
                        src={preview.rows} 
                        collapsed={2}
                        name="data"
                        collapseStringsAfterLength={80}
                      />
                    </div>
                  </div>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default MinioBrowserPage;
