import React, { useEffect, useMemo, useState } from 'react';
import { Container, Row, Col, ListGroup, Button, Breadcrumb, Spinner, Table, Form, Card, InputGroup, Alert, Badge, OverlayTrigger, Tooltip } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import { minioList, minioPreviewParquet, MinioListResponse, ParquetPreview } from '../api/backendRequests';
import { FaFolder, FaFileAlt, FaSync, FaLevelUpAlt, FaHome, FaSearch, FaEye, FaCopy } from 'react-icons/fa';

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

              <div className="mb-2 fw-semibold">Folders</div>
        <ListGroup variant="flush" className="mb-3">
                {filteredFolders.length === 0 && (
          <ListGroup.Item className="text-body-secondary">No folders</ListGroup.Item>
                )}
                {filteredFolders.map((p) => {
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

              <div className="mb-2 fw-semibold">Files</div>
        <ListGroup variant="flush">
                {filteredFiles.length === 0 && (
          <ListGroup.Item className="text-body-secondary">No files</ListGroup.Item>
                )}
                {filteredFiles.map((f) => {
                  const name = f.split('/').pop() || f;
                  const isParquet = name.toLowerCase().endsWith('.parquet');
                  return (
                    <ListGroup.Item action key={f} onClick={() => previewParquet(f)} className="d-flex align-items-center justify-content-between">
                      <div className="d-flex align-items-center flex-grow-1" style={{ minWidth: 0 }}>
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
                <div style={{ overflowX: 'auto', maxHeight: 520 }}>
                  <Table striped bordered hover size="sm" responsive>
                    <thead className="table-light" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                      <tr>
                        {Object.keys(preview.schema).map((col) => (
                          <th key={col}>
                            {col}
                            <div className="text-muted" style={{ fontSize: '0.75rem' }}>{preview.schema[col]}</div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((row, idx) => (
                        <tr key={idx}>
                          {Object.keys(preview.schema).map((col) => {
                            const value = (row as Record<string, unknown>)[col];
                            return <td key={col}>{String(value)}</td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
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
