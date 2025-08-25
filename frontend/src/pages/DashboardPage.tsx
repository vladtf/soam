import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Button, Modal, Form, Spinner, Alert, ButtonGroup, Card, Badge } from 'react-bootstrap';
import { Responsive, WidthProvider, Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { toast } from 'react-toastify';
import { useDashboardData } from '../hooks/useDashboardData';
import StatisticsCards from '../components/StatisticsCards';
import TemperatureChart from '../components/TemperatureChart';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import TemperatureAlertsCard from '../components/TemperatureAlertsCard';
import PageHeader from '../components/PageHeader';
import EnrichmentStatusCard from '../components/EnrichmentStatusCard';
import { DashboardTile } from '../components/DashboardTile';
import { DashboardTileDef, fetchDashboardTileExamples, listDashboardTiles, createDashboardTile, listComputations, previewDashboardTile, previewComputation, deleteDashboardTile, updateDashboardTile } from '../api/backendRequests';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import WithTooltip from '../components/WithTooltip';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';
import { extractDashboardTileErrorMessage } from '../utils/errorHandling';

// Default refresh interval in milliseconds
const DEFAULT_REFRESH_INTERVAL_MS = 30000;

const DashboardPage: React.FC = () => {
  const {
    averageTemperature,
    loading,
    refreshingTemperature,
    timeRange,
    setTimeRange,
    sparkMasterStatus,
    loadingSparkStatus,
    refreshingSparkStatus,
    temperatureAlerts,
    loadingAlerts,
    refreshingAlerts,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refreshAll,
    refreshAlerts,
  } = useDashboardData();

  // User-defined dashboard tiles
  const [tiles, setTiles] = useState<DashboardTileDef[]>([]);
  const [tileLoading, setTileLoading] = useState(false);
  const [showTileModal, setShowTileModal] = useState(false);
  const [editing, setEditing] = useState<DashboardTileDef | null>(null);
  const [examples, setExamples] = useState<{ id: string; title: string; tile: Omit<DashboardTileDef, 'id'> }[]>([]);
  const [computations, setComputations] = useState<{ id: number; name: string }[]>([]);
  const [layouts, setLayouts] = useState<Record<string, Layout>>({});
  const [configText, setConfigText] = useState<string>('{}');
  const [configValid, setConfigValid] = useState<boolean>(true);
  const [configErrors, setConfigErrors] = useState<string[]>([]);
  const [dragEnabled, setDragEnabled] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [enableStaticCards, setEnableStaticCards] = useState<boolean>(() => {
    try {
      return localStorage.getItem('enableStaticCards') === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('enableStaticCards', enableStaticCards ? '1' : '0');
    } catch {
      // ignore
    }
  }, [enableStaticCards]);

  const validateTile = (tile: Omit<DashboardTileDef, 'id'>, comps: { id: number; name: string }[]) => {
    const errs: string[] = [];
    if (!tile.name?.trim()) errs.push('Name is required.');
    if (!tile.computation_id) errs.push('Computation is required.');
    else if (!comps.some(c => c.id === tile.computation_id)) errs.push('Selected computation does not exist.');
    if (!tile.viz_type) errs.push('viz_type is required.');
    // config must be an object
    if (tile.config == null || typeof tile.config !== 'object' || Array.isArray(tile.config)) errs.push('config must be a JSON object.');
    return errs;
  };

  const handlePreviewComputation = async () => {
    if (!editing?.computation_id) {
      toast.error('Please select a computation first');
      return;
    }

    setPreviewLoading(true);
    try {
      const result = await previewComputation(editing.computation_id);
      setPreviewData(result);
    } catch (error) {
      console.error('Error previewing computation:', error);
      setPreviewData(null);
      toast.error(extractDashboardTileErrorMessage(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCloseModal = () => {
    setShowTileModal(false);
    setPreviewData(null);
    setPreviewLoading(false);
  };

  const loadTiles = async () => {
    setTileLoading(true);
    try {
      const [ts, ex, comps] = await Promise.all([
        listDashboardTiles(),
        fetchDashboardTileExamples(),
        listComputations(),
      ]);
      setTiles(ts);
      // seed layouts from tile.layout if present
      const nextLayouts: Record<string, Layout> = {};
      ts.forEach((t, idx) => {
        const lay = (t.layout as any) || {};
        nextLayouts[String(t.id)] = {
          i: String(t.id),
          x: Number(lay.x ?? 0), // Default to left edge
          y: Number(lay.y ?? idx * 4), // Stack tiles vertically
          w: Number(lay.w ?? 12), // Default to full width
          h: Number(lay.h ?? 4),
          static: false,
        } as Layout;
      });
      setLayouts(nextLayouts);
      setExamples(ex.examples || []);
      setComputations((comps || []).filter((c) => typeof c.id === 'number').map((c) => ({ id: c.id as number, name: c.name })));
    } catch (e) {
      console.warn('Failed loading tiles/examples:', e);
    } finally {
      setTileLoading(false);
    }
  };

  useEffect(() => { loadTiles(); }, []);

  const openNewTile = () => {
    const base: DashboardTileDef = { 
      name: '', 
      computation_id: 0, 
      viz_type: 'table', 
      config: { 
        refreshInterval: DEFAULT_REFRESH_INTERVAL_MS, // use constant
        autoRefresh: true 
      }, 
      enabled: true 
    };
    setEditing(base);
    setConfigText(JSON.stringify(base.config, null, 2));
    setConfigValid(true);
    setConfigErrors([]);
    setShowTileModal(true);
  };

  const openEditTile = (tile: DashboardTileDef) => {
    setEditing({ ...tile });
    setConfigText(JSON.stringify(tile.config || {}, null, 2));
    setConfigValid(true);
    setConfigErrors(validateTile(tile as any, computations));
    setShowTileModal(true);
  };

  const onSaveTile = async () => {
    if (!editing) return;
    try {
      const errs = validateTile(editing as Omit<DashboardTileDef, 'id'>, computations);
      if (errs.length) { setConfigErrors(errs); return; }
      
      if (editing.id) {
        await updateDashboardTile(editing.id, {
          name: editing.name,
          computation_id: editing.computation_id,
          viz_type: editing.viz_type,
          config: editing.config,
          enabled: editing.enabled,
        });
        toast.success('Dashboard tile updated successfully');
        toast.success('Dashboard tile updated successfully');
      } else {
        // Create new tile with default layout
        const currentTileCount = tiles.length;
        const defaultLayout = {
          w: 12, // Full width container (12 columns)
          h: 24, // Fixed height
          x: 0, // Start at left edge
          y: currentTileCount * 6 // Stack tiles vertically
        };
        
        const tileData = {
          ...editing,
          layout: defaultLayout
        };
        await createDashboardTile(tileData);
        toast.success('Dashboard tile created successfully');
      }
      setShowTileModal(false);
      setPreviewData(null); // Clear preview data
      await loadTiles();
    } catch (e) {
      toast.error(extractDashboardTileErrorMessage(e));
    }
  };

  return (
    <Container className="pt-3 pb-4">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of key metrics and cluster status"
        onRefresh={refreshAll}
        refreshing={loading || loadingSparkStatus || loadingAlerts || refreshingTemperature || refreshingSparkStatus || refreshingAlerts}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={setAutoRefresh}
        lastUpdated={lastUpdated}
        right={
          <div className="d-flex align-items-center gap-3">
            <WithTooltip tip="Show or hide the static cards section">
              <Form.Check
                type="switch"
                id="static-cards"
                label="Static cards"
                checked={enableStaticCards}
                onChange={(e) => setEnableStaticCards(e.target.checked)}
              />
            </WithTooltip>
            <WithTooltip tip="Enable to rearrange tiles by dragging the ⠿ handle">
              <Form.Check
                type="switch"
                id="drag-mode"
                label="Drag mode"
                checked={dragEnabled}
                onChange={(e) => setDragEnabled(e.target.checked)}
              />
            </WithTooltip>
            <WithTooltip tip="Create a new dashboard tile">
              <Button size="sm" onClick={openNewTile}>New Tile</Button>
            </WithTooltip>
          </div>
        }
      />

      {/* Statistics Cards (static charts) */}
      {enableStaticCards && <StatisticsCards />}

      {/* Spark Applications */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <SparkApplicationsCard
            sparkMasterStatus={sparkMasterStatus}
            loading={loadingSparkStatus}
            refreshing={refreshingSparkStatus}
            lastUpdated={lastUpdated}
          />
        </Col>
      </Row>

      {/* Temperature Chart */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <EnrichmentStatusCard 
            minutes={10} 
            autoRefresh={autoRefresh}
            refreshInterval={30000}
          />
        </Col>
      </Row>



      {/* Temperature Alerts */}
      <Row className="g-3 mt-1">
        <Col md={8}>
          <TemperatureChart
            data={averageTemperature}
            loading={loading}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
            lastUpdated={lastUpdated}
          />
        </Col>
        <Col md={4}>
          <TemperatureAlertsCard
            alerts={temperatureAlerts}
            loading={loadingAlerts}
            lastUpdated={lastUpdated}
            onRefresh={refreshAlerts}
          />
        </Col>
      </Row>

      {/* User-defined tiles in grid */}
      {dragEnabled ? (
        <div className="small text-primary mt-2">Drag is ON. Use the <span className="user-select-none">⠿</span> handle next to each tile title to move tiles. Toggle off to finish arranging.</div>
      ) : (
        <div className="small text-body-secondary mt-2">Drag is OFF. Enable "Drag mode" to rearrange tiles.</div>
      )}
      {tileLoading ? (
        <div className="text-body-secondary"><Spinner animation="border" size="sm" className="me-2" />Loading tiles…</div>
      ) : (
        <ResponsiveGrid
          className="layout mt-3"
          rowHeight={30}
          cols={{ lg: 12, md: 12, sm: 12, xs: 12, xxs: 12 }}
          layouts={{ lg: Object.values(layouts) }}
          draggableCancel=".tile-controls, .btn, input, textarea, select, label, .no-drag"
          draggableHandle={dragEnabled ? ".tile-drag-handle" : undefined}
          isDraggable={dragEnabled}
          isResizable={dragEnabled}
          onLayoutChange={(cur: Layout[]) => {
            if (!dragEnabled) return; // ignore layout changes when drag is disabled
            // persist each tile layout
            cur.forEach((l: Layout) => {
              const t = tiles.find(tt => String(tt.id) === l.i);
              if (!t) return;
              const lay = { x: l.x, y: l.y, w: l.w, h: l.h };
              // optimistic update
              setLayouts(prev => ({ ...prev, [String(t.id)]: { ...l } as Layout }));
              // persist
              if (t.id) updateDashboardTile(t.id, { layout: lay }).catch(() => void 0);
            });
          }}
        >
          {tiles.filter(t => t.enabled !== false).map((t) => (
            <div key={String(t.id)} data-grid={layouts[String(t.id)] || { i: String(t.id), x: 0, y: 0, w: 4, h: 4 }}>
              <TileWithData tile={t} dragEnabled={dragEnabled}
                onDelete={async () => { 
                  if (t.id) { 
                    try {
                      await deleteDashboardTile(t.id); 
                      toast.success('Dashboard tile deleted successfully');
                      await loadTiles(); 
                    } catch (error) {
                      toast.error(extractDashboardTileErrorMessage(error));
                    }
                  } 
                }}
                onEdit={() => openEditTile(t)}
              />
            </div>
          ))}
        </ResponsiveGrid>
      )}

      {/* Builder modal */}
      <Modal show={showTileModal} onHide={handleCloseModal} size="xl">
        <Modal.Header closeButton><Modal.Title>New Dashboard Tile</Modal.Title></Modal.Header>
        <Modal.Body>
          {examples.length > 0 && (
            <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
              <span className="text-body-secondary small">Examples:</span>
              {examples.map(ex => (
                <Button key={ex.id} size="sm" variant="outline-secondary" onClick={() => {
                  setEditing(s => ({ ...(s as DashboardTileDef), ...ex.tile }));
                  setConfigText(JSON.stringify(ex.tile.config || {}, null, 2));
                  const errs = validateTile(ex.tile as Omit<DashboardTileDef, 'id'>, computations);
                  setConfigErrors(errs);
                }}>{ex.title}</Button>
              ))}
            </div>
          )}
          <Row className="g-3">
            <Col md={6}>
              <Form.Group>
                <Form.Label>Name</Form.Label>
                <Form.Control value={editing?.name ?? ''} onChange={(e) => setEditing(s => ({ ...(s as DashboardTileDef), name: e.target.value }))} />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Computation</Form.Label>
                <div className="d-flex gap-2">
                  <Form.Select 
                    value={editing?.computation_id ?? 0} 
                    onChange={(e) => {
                      setEditing(s => ({ ...(s as DashboardTileDef), computation_id: Number(e.target.value) }));
                      setPreviewData(null); // Clear preview when computation changes
                    }}
                    className="flex-grow-1"
                  >
                    <option value={0}>Select…</option>
                    {computations.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
                  </Form.Select>
                  <Button 
                    variant="outline-info" 
                    size="sm" 
                    onClick={handlePreviewComputation}
                    disabled={!editing?.computation_id || previewLoading}
                    style={{ minWidth: '80px' }}
                  >
                    {previewLoading ? <Spinner size="sm" /> : '👁️ Preview'}
                  </Button>
                </div>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Visualization</Form.Label>
                <Form.Select value={editing?.viz_type ?? 'table'} onChange={(e) => setEditing(s => ({ ...(s as DashboardTileDef), viz_type: e.target.value as 'table' | 'stat' | 'timeseries' }))}>
                  <option value="table">table</option>
                  <option value="stat">stat</option>
                  <option value="timeseries">timeseries</option>
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={6} className="d-flex align-items-end">
              <Form.Check type="switch" id="tile-enabled" label="Enabled" checked={!!editing?.enabled} onChange={(e) => setEditing(s => ({ ...(s as DashboardTileDef), enabled: e.target.checked }))} />
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Refresh Interval (seconds)</Form.Label>
                <Form.Control 
                  type="number" 
                  min="5" 
                  max="3600" 
                  value={Number((editing?.config as any)?.refreshInterval ?? DEFAULT_REFRESH_INTERVAL_MS) / 1000} 
                  onChange={(e) => {
                    const seconds = Number(e.target.value);
                    const ms = seconds * 1000;
                    setEditing(s => ({ 
                      ...(s as DashboardTileDef), 
                      config: { ...(s?.config || {}), refreshInterval: ms }
                    }));
                    setConfigText(JSON.stringify({ ...(editing?.config || {}), refreshInterval: ms }, null, 2));
                  }} 
                />
                <Form.Text className="text-muted">
                  How often to automatically refresh tile data (5-3600 seconds)
                </Form.Text>
              </Form.Group>
            </Col>
            <Col md={6} className="d-flex align-items-end">
              <Form.Check 
                type="switch" 
                id="tile-auto-refresh" 
                label="Auto-refresh" 
                checked={(editing?.config as any)?.autoRefresh !== false} 
                onChange={(e) => {
                  setEditing(s => ({ 
                    ...(s as DashboardTileDef), 
                    config: { ...(s?.config || {}), autoRefresh: e.target.checked }
                  }));
                  setConfigText(JSON.stringify({ ...(editing?.config || {}), autoRefresh: e.target.checked }, null, 2));
                }} 
              />
            </Col>
            
            {/* Preview Section */}
            {previewData && (
              <Col md={12}>
                <Card className="mb-3">
                  <Card.Header className="d-flex justify-content-between align-items-center py-2">
                    <span className="fw-bold">Computation Preview</span>
                    <Badge bg="info">{previewData.length} rows</Badge>
                  </Card.Header>
                  <Card.Body>
                    {previewData.length > 0 ? (
                      <div>
                        {/* Column Information */}
                        <div className="mb-3">
                          <h6 className="mb-2">Available Columns:</h6>
                          <div className="d-flex flex-wrap gap-2 mb-2">
                            {Object.keys(previewData[0] || {}).map(colName => {
                              const sampleValue = (previewData[0] as any)?.[colName];
                              const valueType = Array.isArray(sampleValue) ? 'array' : typeof sampleValue;
                              return (
                                <Button
                                  key={colName}
                                  variant="outline-secondary"
                                  size="sm"
                                  onClick={() => {
                                    navigator.clipboard.writeText(colName);
                                    toast.success(`Copied "${colName}" to clipboard`);
                                  }}
                                  className="text-start"
                                >
                                  <div>
                                    <strong>{colName}</strong>
                                    <br />
                                    <small className="text-muted">{valueType}</small>
                                  </div>
                                </Button>
                              );
                            })}
                          </div>
                          <small className="text-muted mb-2 d-block">
                            💡 Click column names to copy them for use in the config below
                          </small>
                          {editing?.viz_type === 'table' && (
                            <div className="alert alert-info py-2 mb-2">
                              <small>
                                📏 <strong>Layout:</strong> Table tiles will be created at full width 
                                (showing {previewData.length} rows). You can resize and reposition them afterwards.
                              </small>
                            </div>
                          )}
                        </div>
                        
                        {/* Sample Data */}
                        <div>
                          <h6 className="mb-2">Sample Data:</h6>
                          <div style={{ fontSize: '0.85rem', maxHeight: '200px', overflowY: 'auto' }}>
                            <pre className="mb-0" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                              {JSON.stringify(previewData.slice(0, 3), null, 2)}
                            </pre>
                            {previewData.length > 3 && (
                              <div className="text-muted text-center mt-2">
                                <small>... showing first 3 rows of {previewData.length}</small>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-muted text-center py-3">
                        <small>No data returned from computation</small>
                      </div>
                    )}
                  </Card.Body>
                </Card>
              </Col>
            )}
            
            <Col md={12}>
              <Form.Group>
                <Form.Label>Config (JSON)</Form.Label>
                <Form.Control as="textarea" rows={10} value={configText} isInvalid={!configValid}
                  onChange={(e) => {
                    const text = e.target.value; setConfigText(text);
                    try {
                      const obj = JSON.parse(text);
                      setConfigValid(true);
                      setEditing(s => ({ ...(s as DashboardTileDef), config: obj }));
                      const errs = validateTile({ ...(editing as DashboardTileDef), config: obj }, computations);
                      setConfigErrors(errs);
                    } catch { setConfigValid(false); setConfigErrors([]); }
                  }}
                />
                <Form.Control.Feedback type="invalid">Invalid JSON</Form.Control.Feedback>
                <Form.Text className="text-muted">
                  Additional configuration options in JSON format. Common settings:
                  <br />• <code>refreshInterval</code>: Refresh interval in milliseconds (default: 30000)
                  <br />• <code>autoRefresh</code>: Enable automatic refresh (default: true)
                  <br />• <code>cacheSec</code>: Cache duration in seconds
                  <br />• <code>columns</code>: Array of column names for table visualization
                  <br />• <code>valueField</code>: Field name for stat visualization
                  <br />• <code>timeField</code>: Time field for timeseries (default: 'time_start')
                  <br />• <code>chartHeight</code>: Height in pixels for timeseries charts
                </Form.Text>
                {configErrors.length > 0 && configValid && (
                  <Alert variant="danger" className="mt-2 mb-0 py-2">
                    <div className="fw-bold small mb-1">Issues:</div>
                    <ul className="mb-0 small">{configErrors.map((er, idx) => (<li key={idx}>{er}</li>))}</ul>
                  </Alert>
                )}
              </Form.Group>
            </Col>
          </Row>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseModal}>Cancel</Button>
          <Button onClick={onSaveTile} disabled={!editing || !configValid || configErrors.length > 0 || !editing?.name?.trim() || !editing?.computation_id}>Save</Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default DashboardPage;

// Helper component to fetch and render tile data
const TileWithData: React.FC<{ tile: DashboardTileDef; dragEnabled: boolean; onDelete?: () => void; onEdit?: () => void }> = ({ tile, dragEnabled, onDelete, onEdit }) => {
  const [rows, setRows] = useState<unknown[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [tsKey, setTsKey] = useState<number>(0);
  const [cache, setCache] = useState<{ rows: unknown[]; at: number } | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Get refresh interval from config, default to 30 seconds
  const refreshIntervalMs = Number((tile.config as any)?.refreshInterval ?? DEFAULT_REFRESH_INTERVAL_MS);
  const autoRefreshEnabled = (tile.config as any)?.autoRefresh !== false;

  useEffect(() => {
    let mounted = true;
    const hasExistingData = rows !== null;
    
    if (hasExistingData) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    
    (async () => {
      try {
        const cacheSec = Number((tile.config as any)?.cacheSec ?? 0);
        if (cache && (Date.now() - cache.at) / 1000 < cacheSec) { 
          setRows(cache.rows); 
          setLastRefreshed(new Date(cache.at));
          return; 
        }
        const data = await previewDashboardTile(tile.id!);
        if (!mounted) return;
        const arr = Array.isArray(data) ? data : [];
        setRows(arr);
        const now = Date.now();
        setCache({ rows: arr, at: now });
        setLastRefreshed(new Date(now));
      } catch {
        if (!mounted) return;
        // Don't clear existing data on error if we have it
        if (!hasExistingData) {
          setRows([]);
        }
      } finally {
        if (mounted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();
    return () => { mounted = false; };
  }, [tile.id, tsKey, rows]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefreshEnabled || refreshIntervalMs <= 0) return;
    
    const interval = setInterval(() => {
      setTsKey(k => k + 1);
      setCache(null);
    }, refreshIntervalMs);
    
    return () => {
      clearInterval(interval);
    };
  }, [autoRefreshEnabled, refreshIntervalMs, tile.id]);

  const handleManualRefresh = () => {
    setTsKey(k => k + 1);
    setCache(null);
  };

  return (
    <div className="h-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center mb-1">
        <div className="fw-semibold d-flex align-items-center gap-2" title={dragEnabled ? 'Drag to move tile' : ''}>
          <span
            className="tile-drag-handle user-select-none"
            aria-label="Drag handle"
            style={{ cursor: dragEnabled ? 'grab' as const : 'default' as const }}
          >
            ⠿
          </span>
          <span>{tile.name}</span>
        </div>
        <ButtonGroup size="sm" className="tile-controls" onMouseDown={(e) => e.stopPropagation()}>
          <WithTooltip tip="Reload the data for this tile">
            <Button variant="outline-secondary" onClick={(e) => { e.stopPropagation(); handleManualRefresh(); }}>Refresh</Button>
          </WithTooltip>
          <WithTooltip tip="Edit tile settings (computation, visualization, config)">
            <Button variant="outline-secondary" onClick={(e) => { e.stopPropagation(); onEdit && onEdit(); }}>Edit</Button>
          </WithTooltip>
          <WithTooltip tip="Remove this tile from the dashboard">
            <Button variant="outline-danger" onClick={(e) => { e.stopPropagation(); onDelete && onDelete(); }}>Delete</Button>
          </WithTooltip>
        </ButtonGroup>
      </div>
      
      {/* Refresh status info */}
      <div className="small text-body-secondary mb-2 d-flex justify-content-between align-items-center">
        <span>
          {refreshing ? (
            <span className="text-primary">
              <Spinner animation="border" size="sm" className="me-1" />
              Refreshing...
            </span>
          ) : lastRefreshed ? (
            `Updated ${formatRelativeTime(lastRefreshed)}`
          ) : (
            'Not refreshed yet'
          )}
        </span>
        <span>
          {autoRefreshEnabled ? formatRefreshPeriod(refreshIntervalMs) : 'Manual refresh only'}
        </span>
      </div>

      <div className="flex-grow-1 d-flex flex-column" style={{ minHeight: 0 }}>
        {loading && rows === null ? (
          <div className="text-body-secondary border rounded p-2 bg-body-tertiary">
            <Spinner animation="border" size="sm" className="me-2" />Loading…
          </div>
        ) : tile.viz_type === 'timeseries' ? (
          <div className="border rounded p-2 bg-body-tertiary">
            <ResponsiveContainer width="100%" height={Math.max(120, Number((tile.config as any)?.chartHeight ?? 200))}>
              <LineChart data={(rows as any[]) || []}>
                <XAxis dataKey={(tile.config as any)?.timeField || 'time_start'} hide={false} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey={(tile.config as any)?.valueField || 'avg_temp'} stroke="#3388ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex-grow-1" style={{ minHeight: 0 }}>
            <DashboardTile title={''} viz={tile.viz_type as 'table' | 'stat' | 'timeseries'} data={rows || []} config={tile.config} />
          </div>
        )}
      </div>
    </div>
  );
};

const ResponsiveGrid = WidthProvider(Responsive);
