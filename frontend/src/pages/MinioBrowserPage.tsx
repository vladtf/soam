import React, { useEffect, useMemo, useState } from 'react';
import { Container, Row, Col, ListGroup, Button, Breadcrumb, Spinner, Form, Card, InputGroup, Alert, Badge, OverlayTrigger, Tooltip } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import { minioList, minioFind, minioPreviewParquet, MinioListResponse, MinioObjectInfo, ParquetPreview, minioDeleteObjects, minioDeletePrefix, MinioPaginatedResponse, MinioFindOptions } from '../api/backendRequests';
import { FaFolder, FaFileAlt, FaSync, FaLevelUpAlt, FaHome, FaSearch, FaEye, FaCopy, FaTable, FaCode } from 'react-icons/fa';
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
  const [autoDrill, setAutoDrill] = useState<boolean>(true);
  const [isDrilling, setIsDrilling] = useState<boolean>(false);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [foldersPage, setFoldersPage] = useState<number>(1);
  const [foldersPageSize, setFoldersPageSize] = useState<number>(10);
  const [disableAutoDrillOnce, setDisableAutoDrillOnce] = useState<boolean>(false);
  
  // File info, sorting, and server-side pagination
  const [fileInfos, setFileInfos] = useState<MinioObjectInfo[]>([]);
  const [sortBy, setSortBy] = useState<"name" | "size">("size");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [showOnlyNonEmpty, setShowOnlyNonEmpty] = useState<boolean>(false);
  const [minFileSize, setMinFileSize] = useState<number>(500);
  
  // Server-side pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(0);
  const [hasNext, setHasNext] = useState<boolean>(false);
  const [hasPrev, setHasPrev] = useState<boolean>(false);
  
  // Client-side caching for preloading
  const [pageCache, setPageCache] = useState<Map<string, MinioPaginatedResponse>>(new Map());
  const [preloadingPages, setPreloadingPages] = useState<Set<number>>(new Set());

  // Generate cache key for pagination requests
  const getCacheKey = (prefix: string, page: number, pageSize: number, sortBy: string, sortOrder: string, minSize: number): string => {
    return `${prefix}|${page}|${pageSize}|${sortBy}|${sortOrder}|${minSize}`;
  };

  // Load paginated files with caching
  const loadFiles = async (targetPrefix: string, page: number = 1): Promise<MinioPaginatedResponse | null> => {
    const cacheKey = getCacheKey(targetPrefix, page, pageSize, sortBy, sortOrder, showOnlyNonEmpty ? minFileSize : 0);
    
    // Check cache first
    if (pageCache.has(cacheKey)) {
      return pageCache.get(cacheKey)!;
    }
    
    try {
      const options: MinioFindOptions = {
        prefix: targetPrefix,
        sortBy,
        minSize: showOnlyNonEmpty ? minFileSize : 0,
        page,
        pageSize
      };
      
      const response = await minioFind(options);
      
      // Cache the response
      setPageCache(prev => new Map(prev).set(cacheKey, response));
      
      return response;
    } catch (e) {
      console.warn("Failed to load paginated files:", e);
      return null;
    }
  };

  // Preload adjacent pages for smooth navigation
  const preloadAdjacentPages = async (targetPrefix: string, currentPage: number) => {
    const pagesToPreload = [currentPage - 1, currentPage + 1].filter(p => p > 0);
    
    for (const page of pagesToPreload) {
      const cacheKey = getCacheKey(targetPrefix, page, pageSize, sortBy, sortOrder, showOnlyNonEmpty ? minFileSize : 0);
      
      if (!pageCache.has(cacheKey) && !preloadingPages.has(page)) {
        setPreloadingPages(prev => new Set(prev).add(page));
        
        try {
          const options: MinioFindOptions = {
            prefix: targetPrefix,
            sortBy,
            minSize: showOnlyNonEmpty ? minFileSize : 0,
            page,
            pageSize
          };
          
          const response = await minioFind(options);
          setPageCache(prev => new Map(prev).set(cacheKey, response));
        } catch (e) {
          console.warn(`Failed to preload page ${page}:`, e);
        } finally {
          setPreloadingPages(prev => {
            const next = new Set(prev);
            next.delete(page);
            return next;
          });
        }
      }
    }
  };

  // Pre-calculate the final folder destination by following single-folder chains
  const findFinalDestination = async (startPath: string): Promise<string> => {
    let currentPath = startPath;
    const visited = new Set<string>(); // Prevent infinite loops
    
    while (visited.size < 50) { // Safety limit
      if (visited.has(currentPath)) break;
      visited.add(currentPath);
      
      try {
        const res = await minioList(currentPath);
        // If folder has files or multiple subfolders, this is the final destination
        if (res.files.length > 0 || res.prefixes.length !== 1) {
          return currentPath;
        }
        // Continue to the single subfolder
        currentPath = res.prefixes[0];
      } catch (e) {
        // If we can't load, return the current path
        return currentPath;
      }
    }
    return currentPath;
  };

  const load = async (p: string, enableAutoDrill = true, page = 1) => {
    setLoading(true);
    setError(null);
    setIsDrilling(false);
    try {
      let finalPath = p;
      
      // If auto-drill is enabled and not disabled for this navigation, find the final destination
      if (enableAutoDrill && autoDrill && !disableAutoDrillOnce) {
        setIsDrilling(true);
        finalPath = await findFinalDestination(p);
        if (finalPath !== p) {
          // Update the prefix to the final destination
          setPrefix(finalPath);
          setIsDrilling(false);
          return; // The useEffect will trigger and load the final path
        }
      }
      
      // Reset the disable flag after checking
      if (disableAutoDrillOnce) {
        setDisableAutoDrillOnce(false);
      }
      
      const res = await minioList(finalPath);
      setListing(res);
      
      // Also fetch detailed file information with server-side pagination
      if (res.files.length > 0) {
        try {
          const fileResponse = await loadFiles(finalPath, page);
          if (fileResponse) {
            setFileInfos(fileResponse.items);
            setTotalItems(fileResponse.pagination.total_items);
            setTotalPages(fileResponse.pagination.total_pages);
            setCurrentPage(fileResponse.pagination.page);
            setHasNext(fileResponse.pagination.has_next);
            setHasPrev(fileResponse.pagination.has_prev);
            
            // Preload adjacent pages for smooth navigation
            preloadAdjacentPages(finalPath, fileResponse.pagination.page);
          } else {
            setFileInfos([]);
            setTotalItems(0);
            setTotalPages(0);
            setCurrentPage(1);
            setHasNext(false);
            setHasPrev(false);
          }
        } catch (e) {
          console.warn("Failed to fetch file details:", e);
          setFileInfos([]);
          setTotalItems(0);
          setTotalPages(0);
          setCurrentPage(1);
          setHasNext(false);
          setHasPrev(false);
        }
      } else {
        setFileInfos([]);
        setTotalItems(0);
        setTotalPages(0);
        setCurrentPage(1);
        setHasNext(false);
        setHasPrev(false);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
      setIsDrilling(false);
    }
  };

  useEffect(() => {
    load(prefix);
  }, [prefix]);

  // Reload file details when sorting or pagination options change, debounced to avoid rapid API calls
  useEffect(() => {
    if (fileInfos.length > 0) {
      const handler = setTimeout(() => {
        load(prefix, false, 1); // Don't auto-drill when just refreshing for sorting, reset to page 1
      }, 300); // 300ms debounce
      return () => clearTimeout(handler);
    }
  }, [sortBy, sortOrder, showOnlyNonEmpty, minFileSize, pageSize]);

  // Clear cache when settings change
  useEffect(() => {
    setPageCache(new Map());
    setCurrentPage(1);
  }, [prefix, sortBy, sortOrder, showOnlyNonEmpty, minFileSize, pageSize]);

  // Page navigation handlers
  const goToPage = async (page: number) => {
    if (page < 1 || page > totalPages) return;
    
    setLoading(true);
    try {
      const response = await loadFiles(prefix, page);
      if (response) {
        setFileInfos(response.items);
        setCurrentPage(response.pagination.page);
        setHasNext(response.pagination.has_next);
        setHasPrev(response.pagination.has_prev);
        
        // Preload adjacent pages
        preloadAdjacentPages(prefix, response.pagination.page);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const nextPage = () => goToPage(currentPage + 1);
  const prevPage = () => goToPage(currentPage - 1);

  const goTo = (p: string) => {
    setPreviewKey(null);
    setPreview(null);
    setPrefix(p);
    setSelected({});
    // Load will be called automatically by useEffect when prefix changes
  };

  const goToManual = (p: string) => {
    setPreviewKey(null);
    setPreview(null);
    setIsDrilling(false); // Clear drilling state for manual navigation
    setDisableAutoDrillOnce(true); // Disable auto-drill for this navigation
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
    goToManual(up);
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
    if (checked) filteredFiles.forEach((f) => { next[f.key] = true; });
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
    
    // Use server-side paginated data directly (already sorted and filtered by backend)
    return fileInfos.filter((f) => {
      const name = f.key.split('/').pop() || f.key;
      const parquetOk = !onlyParquet || name.toLowerCase().endsWith('.parquet');
      return parquetOk && name.toLowerCase().includes(q);
    });
  }, [fileInfos, filter, onlyParquet]);

  const allSelected = useMemo(() => {
    const keys = filteredFiles.map(f => f.key);
    if (keys.length === 0) return false;
    return keys.every((k) => selected[k]);
  }, [filteredFiles, selected]);

  // Pagination calculations for folders only (files use server-side pagination)
  const foldersPages = Math.max(1, Math.ceil(filteredFolders.length / Math.max(1, foldersPageSize)));

  useEffect(() => {
    setFoldersPage(1);
  }, [filter, listing.prefixes, foldersPageSize]);

  useEffect(() => {
    if (foldersPage > foldersPages) setFoldersPage(foldersPages);
  }, [foldersPages]);

  const visibleFolders = useMemo(() => {
    const start = (foldersPage - 1) * foldersPageSize;
    return filteredFolders.slice(start, start + foldersPageSize);
  }, [filteredFolders, foldersPage, foldersPageSize]);

  // Utility function to format file sizes
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const refresh = () => load(prefix, true); // Enable auto-drill on refresh

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
            <Button variant="outline-danger" onClick={deleteSelected} disabled={Object.keys(selected).filter((k) => selected[k]).length === 0} title="Delete selected files">
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
            <Breadcrumb.Item onClick={() => goToManual('')} role="button" aria-label="Root" title="Root">
              <FaHome className="me-1" /> /
            </Breadcrumb.Item>
            {breadcrumbParts.map((b, i) => (
              <Breadcrumb.Item key={b.path} active={i === breadcrumbParts.length - 1} onClick={() => goToManual(b.path)} role="button">
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
              <div className="d-flex align-items-center">
                <span>Browse</span>
                {isDrilling && (
                  <Badge bg="info" className="ms-2 d-flex align-items-center">
                    <Spinner animation="border" size="sm" className="me-1" />
                    Auto-navigating...
                  </Badge>
                )}
              </div>
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
                className="mb-2"
              />
              <Form.Check
                type="checkbox"
                id="autoDrill"
                label="Auto-navigate through folders with single child"
                checked={autoDrill}
                onChange={(e) => setAutoDrill(e.target.checked)}
                className="mb-2"
                title="Automatically navigate through folders that contain only one subfolder"
              />
              
              {/* File Sorting and Filtering Controls */}
              <div className="mb-3 p-2 bg-body-tertiary rounded">
                <div className="small fw-semibold mb-2">File Options:</div>
                <Row className="g-2">
                  <Col sm={6}>
                    <Form.Check
                      type="checkbox"
                      id="showOnlyNonEmpty"
                      label="Hide small files"
                      checked={showOnlyNonEmpty}
                      onChange={(e) => setShowOnlyNonEmpty(e.target.checked)}
                      className="small"
                    />
                  </Col>
                  <Col sm={6}>
                    <InputGroup size="sm">
                      <InputGroup.Text>Min</InputGroup.Text>
                      <Form.Control
                        type="number"
                        min={0}
                        max={10000}
                        value={minFileSize}
                        onChange={(e) => setMinFileSize(Number(e.target.value))}
                        style={{ maxWidth: '5rem' }}
                      />
                      <InputGroup.Text>B</InputGroup.Text>
                    </InputGroup>
                  </Col>
                </Row>
                <Row className="g-2 mt-1">
                  <Col sm={6}>
                    <Form.Select size="sm" value={sortBy} onChange={(e) => setSortBy(e.target.value as "name" | "size")}>
                      <option value="name">Sort by name</option>
                      <option value="size">Sort by size</option>
                    </Form.Select>
                  </Col>
                  <Col sm={6}>
                    <Form.Select size="sm" value={sortOrder} onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}>
                      <option value="asc">{sortBy === "size" ? "Smallest first" : "A-Z"}</option>
                      <option value="desc">{sortBy === "size" ? "Largest first" : "Z-A"}</option>
                    </Form.Select>
                  </Col>
                </Row>
              </div>

              <div className="mb-2 fw-semibold d-flex align-items-center justify-content-between">
                <span>Folders:</span>
                <InputGroup size="sm" className="flex-shrink-0" style={{ maxWidth: 'min(320px, 100%)' }}>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFoldersPage((p) => Math.max(1, p - 1))} disabled={foldersPage <= 1}>Prev</Button>
                  <InputGroup.Text>Page {foldersPage}/{foldersPages}</InputGroup.Text>
                  <Button variant="outline-secondary" size="sm" onClick={() => setFoldersPage((p) => Math.min(foldersPages, p + 1))} disabled={foldersPage >= foldersPages}>Next</Button>
                  <InputGroup.Text>Per page</InputGroup.Text>
                  <Form.Select size="sm" value={foldersPageSize} onChange={(e) => setFoldersPageSize(Number(e.target.value))} style={{ minWidth: '5rem', maxWidth: '6rem' }}>
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
                <span>Files:</span>
                <div className="d-flex align-items-center gap-2">
                  {totalItems > 0 && (
                    <Badge bg="secondary" className="fs-6">
                      {totalItems} total
                    </Badge>
                  )}
                  <InputGroup size="sm" className="flex-shrink-0" style={{ maxWidth: 'min(320px, 100%)' }}>
                    <Button variant="outline-secondary" size="sm" onClick={prevPage} disabled={!hasPrev || loading}>Prev</Button>
                    <InputGroup.Text>Page {currentPage}/{totalPages}</InputGroup.Text>
                    <Button variant="outline-secondary" size="sm" onClick={nextPage} disabled={!hasNext || loading}>Next</Button>
                    <InputGroup.Text>Size</InputGroup.Text>
                    <Form.Select size="sm" value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} style={{ minWidth: '4rem', maxWidth: '5rem' }}>
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                      <option value={200}>200</option>
                    </Form.Select>
                  </InputGroup>
                </div>
              </div>
              <div className="mb-2 d-flex align-items-center">
                <Form.Check
                  type="checkbox"
                  id="selectAll"
                  label="Select all"
                  checked={allSelected}
                  onChange={(e) => toggleSelectAll(e.target.checked)}
                />
              </div>
              <ListGroup variant="flush">
                {filteredFiles.length === 0 && (
                  <ListGroup.Item className="text-body-secondary">No files</ListGroup.Item>
                )}
                {filteredFiles.map((f) => {
                  const name = f.key.split('/').pop() || f.key;
                  const isParquet = name.toLowerCase().endsWith('.parquet');
                  const isPreviewedFile = previewKey === f.key;
                  return (
                    <ListGroup.Item
                      action
                      key={f.key}
                      className={`d-flex align-items-center justify-content-between ${isPreviewedFile ? 'bg-primary-subtle border-primary' : ''}`}
                    >
                      <div className="d-flex align-items-center flex-grow-1" style={{ minWidth: 0 }} onClick={() => previewParquet(f.key)}>
                        <Form.Check className="me-2" checked={!!selected[f.key]} onChange={(e) => toggleSelect(f.key, e.target.checked)} onClick={(e) => e.stopPropagation()} />
                        <FaFileAlt className="me-2" />
                        <div className="d-flex flex-column" style={{ minWidth: 0 }}>
                          <OverlayTrigger placement="top" overlay={<Tooltip>{name}</Tooltip>}>
                            <span className="text-truncate" style={{ minWidth: 0, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>{name}</span>
                          </OverlayTrigger>
                          <small className="text-body-secondary">{formatFileSize(f.size)}</small>
                        </div>
                        {isParquet && <Badge bg="secondary" className="ms-2">parquet</Badge>}
                        {f.size === 0 && <Badge bg="warning" className="ms-2">empty</Badge>}
                        {f.size > 0 && f.size < 1000 && <Badge bg="info" className="ms-2">small</Badge>}
                      </div>
                      <Button size="sm" variant="outline-secondary" aria-label={`Preview ${name}`} onClick={(e) => { e.stopPropagation(); previewParquet(f.key); }}>
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
                  <span className="align-middle ms-2 d-inline-flex align-items-center" style={{ maxWidth: 'min(30vw, 480px)' }}>
                    <OverlayTrigger placement="top" overlay={<Tooltip>{previewKey}</Tooltip>}>
                      <Badge bg="light" text="dark" className="text-truncate" style={{ maxWidth: 'min(26vw, 420px)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>{previewKey}</Badge>
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
                <InputGroup size="sm" style={{ minWidth: '8rem', maxWidth: '10rem' }}>
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
                <div style={{ maxHeight: 'min(80vh, 800px)', overflowY: 'auto' }}>
                  {/* Schema Section */}
                  <div className="mb-4 p-3 border rounded bg-light">
                    <div className="d-flex align-items-center mb-3">
                      <h5 className="mb-0 text-primary">
                        <FaCode className="me-2" />
                        Schema
                      </h5>
                    </div>
                    <div className="bg-white p-2 rounded border">
                      <ThemedReactJson
                        src={preview.schema}
                        collapsed={false}
                        name="schema"
                      />
                    </div>
                  </div>

                  {/* Data Section */}
                  <div className="p-3 border rounded bg-light">
                    <div className="d-flex align-items-center justify-content-between mb-3">
                      <h5 className="mb-0 text-success">
                        <FaTable className="me-2" />
                        Data
                      </h5>
                      <Badge bg="secondary" className="fs-6">
                        {preview.rows.length} rows
                      </Badge>
                    </div>
                    <div className="bg-white p-2 rounded border" style={{ maxHeight: 'min(60vh, 600px)', overflowY: 'auto' }}>
                      <ThemedReactJson
                        src={preview.rows}
                        collapsed={false}
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
