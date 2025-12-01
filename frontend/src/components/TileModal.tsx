import React, { useState, useEffect } from 'react';
import { Modal, Form, Button, Row, Col, Card, Badge, Alert, Spinner } from 'react-bootstrap';
import { toast } from 'react-toastify';
import { DashboardTile } from './DashboardTile';
import { DashboardTileDef, previewComputation, previewDashboardTileConfig } from '../api/backendRequests';
import { extractDashboardTileErrorMessage } from '../utils/errorHandling';

// Default refresh interval in milliseconds
const DEFAULT_REFRESH_INTERVAL_MS = 30000;

interface TileModalProps {
  show: boolean;
  editing: DashboardTileDef | null;
  examples: { id: string; title: string; tile: Omit<DashboardTileDef, 'id'> }[];
  computations: { id: number; name: string }[];
  onClose: () => void;
  onSave: (tile: DashboardTileDef) => Promise<void>;
  onEditingChange: (tile: DashboardTileDef | null) => void;
}

export const TileModal: React.FC<TileModalProps> = ({
  show,
  editing,
  examples,
  computations,
  onClose,
  onSave,
  onEditingChange
}) => {
  const [configText, setConfigText] = useState<string>('{}');
  const [configValid, setConfigValid] = useState<boolean>(true);
  const [configErrors, setConfigErrors] = useState<string[]>([]);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [tilePreviewData, setTilePreviewData] = useState<unknown[] | null>(null);
  const [tilePreviewLoading, setTilePreviewLoading] = useState(false);

  // Update config text when editing changes
  useEffect(() => {
    if (editing) {
      setConfigText(JSON.stringify(editing.config || {}, null, 2));
      setConfigValid(true);
      setConfigErrors([]);
    }
  }, [editing]);

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

  const handlePreviewTile = async () => {
    if (!editing?.computation_id) {
      toast.error('Please select a computation first');
      return;
    }

    if (!editing.viz_type) {
      toast.error('Please select a visualization type');
      return;
    }

    setTilePreviewLoading(true);
    try {
      const result = await previewDashboardTileConfig({
        computation_id: editing.computation_id,
        viz_type: editing.viz_type,
        config: editing.config || {}
      });
      
      // Check if computation was deleted
      if (result && typeof result === 'object' && (result as any).error === 'COMPUTATION_DELETED') {
        toast.error((result as any).message);
        setTilePreviewData(null);
        return;
      }
      
      setTilePreviewData(result);
    } catch (error) {
      console.error('Error previewing tile:', error);
      setTilePreviewData(null);
      toast.error(extractDashboardTileErrorMessage(error));
    } finally {
      setTilePreviewLoading(false);
    }
  };

  const handleClose = () => {
    setPreviewData(null);
    setPreviewLoading(false);
    setTilePreviewData(null);
    setTilePreviewLoading(false);
    onClose();
  };

  const handleSave = async () => {
    if (!editing) return;
    try {
      const errs = validateTile(editing as Omit<DashboardTileDef, 'id'>, computations);
      if (errs.length) { 
        setConfigErrors(errs); 
        return; 
      }
      
      await onSave(editing);
      handleClose();
    } catch (e) {
      toast.error(extractDashboardTileErrorMessage(e));
    }
  };

  const updateConfig = (field: string, value: any) => {
    if (!editing) return;
    
    const newConfig = { ...(editing.config || {}), [field]: value };
    onEditingChange({ 
      ...(editing as DashboardTileDef), 
      config: newConfig
    });
    setConfigText(JSON.stringify(newConfig, null, 2));
  };

  const handleSmartColumnClick = (colName: string, suggestion: string) => {
    if (!editing) return;

    if (editing.viz_type === 'timeseries') {
      if (suggestion === '⏰ Time') {
        updateConfig('timeField', colName);
        toast.success(`Set "${colName}" as time field`);
      } else if (suggestion === '📊 Value') {
        updateConfig('valueField', colName);
        toast.success(`Set "${colName}" as value field`);
      } else {
        navigator.clipboard.writeText(colName);
        toast.success(`Copied "${colName}" to clipboard`);
      }
    } else if (editing.viz_type === 'stat') {
      if (suggestion === '📊 Stat') {
        updateConfig('valueField', colName);
        toast.success(`Set "${colName}" as stat value field`);
      } else {
        navigator.clipboard.writeText(colName);
        toast.success(`Copied "${colName}" to clipboard`);
      }
    } else {
      navigator.clipboard.writeText(colName);
      toast.success(`Copied "${colName}" to clipboard`);
    }
  };

  return (
    <Modal show={show} onHide={handleClose} size="xl">
      <Modal.Header closeButton>
        <Modal.Title>
          {editing?.id ? 'Edit Dashboard Tile' : 'New Dashboard Tile'}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {examples.length > 0 && (
          <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
            <span className="text-body-secondary small">Examples:</span>
            {examples.map(ex => (
              <Button 
                key={ex.id} 
                size="sm" 
                variant="outline-secondary" 
                onClick={() => {
                  onEditingChange({ ...(editing as DashboardTileDef), ...ex.tile });
                  const errs = validateTile(ex.tile as Omit<DashboardTileDef, 'id'>, computations);
                  setConfigErrors(errs);
                }}
              >
                {ex.title}
              </Button>
            ))}
          </div>
        )}

        <Row className="g-3">
          <Col md={6}>
            <Form.Group>
              <Form.Label>Name</Form.Label>
              <Form.Control 
                value={editing?.name ?? ''} 
                onChange={(e) => onEditingChange({ ...(editing as DashboardTileDef), name: e.target.value })} 
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group>
              <Form.Label>Computation</Form.Label>
              <div className="d-flex gap-2">
                <Form.Select 
                  value={editing?.computation_id ?? 0} 
                  onChange={(e) => {
                    onEditingChange({ ...(editing as DashboardTileDef), computation_id: Number(e.target.value) });
                    setPreviewData(null);
                    setTilePreviewData(null);
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
                <Button 
                  variant="outline-success" 
                  size="sm" 
                  onClick={handlePreviewTile}
                  disabled={!editing?.computation_id || !editing?.viz_type || tilePreviewLoading}
                  style={{ minWidth: '100px' }}
                >
                  {tilePreviewLoading ? <Spinner size="sm" /> : '🎨 Preview Tile'}
                </Button>
              </div>
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group>
              <Form.Label>Visualization</Form.Label>
              <Form.Select 
                value={editing?.viz_type ?? 'table'} 
                onChange={(e) => onEditingChange({ 
                  ...(editing as DashboardTileDef), 
                  viz_type: e.target.value as 'table' | 'stat' | 'timeseries' 
                })}
              >
                <option value="table">table</option>
                <option value="stat">stat</option>
                <option value="timeseries">timeseries</option>
              </Form.Select>
            </Form.Group>
          </Col>
          <Col md={6} className="d-flex align-items-end">
            <Form.Check 
              type="switch" 
              id="tile-enabled" 
              label="Enabled" 
              checked={!!editing?.enabled} 
              onChange={(e) => onEditingChange({ ...(editing as DashboardTileDef), enabled: e.target.checked })} 
            />
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
                  updateConfig('refreshInterval', ms);
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
              onChange={(e) => updateConfig('autoRefresh', e.target.checked)}
            />
          </Col>
          
          {/* Sensitivity Override */}
          <Col md={6}>
            <Form.Group>
              <Form.Label>Data Sensitivity</Form.Label>
              <Form.Select 
                value={editing?.sensitivity || ''} 
                onChange={(e) => onEditingChange({ 
                  ...(editing as DashboardTileDef), 
                  sensitivity: e.target.value || undefined 
                } as DashboardTileDef)}
              >
                <option value="">Auto (inherit from computation)</option>
                <option value="public">Public</option>
                <option value="internal">Internal</option>
                <option value="confidential">Confidential</option>
                <option value="restricted">Restricted</option>
              </Form.Select>
              <Form.Text className="text-muted">
                {editing?.sensitivity 
                  ? `Custom sensitivity: ${editing.sensitivity.toUpperCase()}`
                  : "Leave as 'Auto' to inherit sensitivity from the linked computation"
                }
              </Form.Text>
            </Form.Group>
          </Col>
          <Col md={6} className="d-flex align-items-end">
            {editing?.sensitivity && (
              <Badge 
                bg={
                  editing.sensitivity === 'restricted' ? 'danger' :
                  editing.sensitivity === 'confidential' ? 'warning' :
                  editing.sensitivity === 'internal' ? 'info' : 'secondary'
                }
                className="text-uppercase"
              >
                {editing.sensitivity}
              </Badge>
            )}
          </Col>
          
          {/* Visualization-specific configuration helpers */}
          {editing?.viz_type === 'timeseries' && (
            <>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Time Field</Form.Label>
                  <Form.Control
                    value={(editing?.config as any)?.timeField || 'time_start'}
                    onChange={(e) => updateConfig('timeField', e.target.value)}
                    placeholder="e.g. time_start, timestamp, date"
                  />
                  <Form.Text className="text-muted">
                    Column name to use for X-axis (time). Common: time_start, timestamp, ingest_ts
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Value Field</Form.Label>
                  <Form.Control
                    value={(editing?.config as any)?.valueField || 'avg_temperature'}
                    onChange={(e) => updateConfig('valueField', e.target.value)}
                    placeholder="e.g. avg_temperature, value, count"
                  />
                  <Form.Text className="text-muted">
                    Column name to use for Y-axis (values). Common: avg_temperature, reading_count
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Chart Height (pixels)</Form.Label>
                  <Form.Control
                    type="number"
                    min="100"
                    max="800"
                    value={(editing?.config as any)?.chartHeight || 200}
                    onChange={(e) => updateConfig('chartHeight', Number(e.target.value))}
                  />
                  <Form.Text className="text-muted">
                    Height of the chart in pixels (100-800)
                  </Form.Text>
                </Form.Group>
              </Col>
            </>
          )}

          {editing?.viz_type === 'stat' && (
            <Col md={6}>
              <Form.Group>
                <Form.Label>Value Field</Form.Label>
                <Form.Control
                  value={(editing?.config as any)?.valueField || 'avg_temperature'}
                  onChange={(e) => updateConfig('valueField', e.target.value)}
                  placeholder="e.g. avg_temperature, count, total"
                />
                <Form.Text className="text-muted">
                  Column name to display as the main statistic value
                </Form.Text>
              </Form.Group>
            </Col>
          )}
          
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
                            
                            // Determine if this column is suitable for time or value based on viz type
                            let suggestion = '';
                            let variant = 'outline-secondary';
                            
                            if (editing?.viz_type === 'timeseries') {
                              if (colName.toLowerCase().includes('time') || colName.toLowerCase().includes('date') || colName.toLowerCase().includes('ts')) {
                                suggestion = '⏰ Time';
                                variant = 'outline-primary';
                              } else if (valueType === 'number' && !colName.toLowerCase().includes('id')) {
                                suggestion = '📊 Value';
                                variant = 'outline-success';
                              }
                            } else if (editing?.viz_type === 'stat') {
                              if (valueType === 'number' && !colName.toLowerCase().includes('id')) {
                                suggestion = '📊 Stat';
                                variant = 'outline-success';
                              }
                            }
                            
                            return (
                              <Button
                                key={colName}
                                variant={variant}
                                size="sm"
                                onClick={() => handleSmartColumnClick(colName, suggestion)}
                                className="text-start"
                              >
                                <div>
                                  <strong>{colName}</strong> {suggestion && <small className="text-muted">({suggestion})</small>}
                                  <br />
                                  <small className="text-muted">{valueType}</small>
                                </div>
                              </Button>
                            );
                          })}
                        </div>
                        
                        {/* Visualization-specific guidance */}
                        {editing?.viz_type === 'timeseries' && (
                          <div className="alert alert-primary py-2 mb-2">
                            <small>
                              🎯 <strong>Timeseries Chart:</strong> Click blue buttons (⏰ Time) to set time field, 
                              green buttons (📊 Value) to set value field. Other columns can be copied to clipboard.
                            </small>
                          </div>
                        )}
                        
                        {editing?.viz_type === 'stat' && (
                          <div className="alert alert-success py-2 mb-2">
                            <small>
                              🎯 <strong>Stat Display:</strong> Click green buttons (📊 Stat) to set the main statistic value. 
                              Other columns can be copied to clipboard.
                            </small>
                          </div>
                        )}
                        
                        {editing?.viz_type === 'table' && (
                          <div className="alert alert-info py-2 mb-2">
                            <small>
                              🎯 <strong>Table Display:</strong> Click column names to copy them for use in configuration. 
                              You can specify which columns to show in the 'columns' config array.
                            </small>
                          </div>
                        )}
                        
                        <small className="text-muted mb-2 d-block">
                          💡 Smart suggestions are highlighted with colors and icons
                        </small>
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
          
          {/* Tile Preview Section */}
          {tilePreviewData && (
            <Col md={12}>
              <Card className="mb-3">
                <Card.Header className="d-flex justify-content-between align-items-center py-2">
                  <span className="fw-bold">🎨 Tile Preview ({editing?.viz_type})</span>
                  <Badge bg="success">{tilePreviewData.length} rows</Badge>
                </Card.Header>
                <Card.Body>
                  {tilePreviewData.length > 0 ? (
                    <div>
                      <div className="border rounded p-2 bg-body-tertiary mb-3">
                        <DashboardTile 
                          title="" 
                          viz={editing?.viz_type as 'table' | 'stat' | 'timeseries'} 
                          data={tilePreviewData} 
                          config={editing?.config || {}} 
                        />
                      </div>
                      <div className="alert alert-info py-2 mb-0">
                        <small>
                          ✨ <strong>This is how your tile will look on the dashboard!</strong> 
                          You can adjust the configuration above to customize the appearance.
                        </small>
                      </div>
                    </div>
                  ) : (
                    <div className="text-muted text-center py-3">
                      <small>No data returned for tile preview</small>
                    </div>
                  )}
                </Card.Body>
              </Card>
            </Col>
          )}
          
          <Col md={12}>
            <Form.Group>
              <Form.Label>Config (JSON)</Form.Label>
              <Form.Control 
                as="textarea" 
                rows={10} 
                value={configText} 
                isInvalid={!configValid}
                onChange={(e) => {
                  const text = e.target.value; 
                  setConfigText(text);
                  try {
                    const obj = JSON.parse(text);
                    setConfigValid(true);
                    onEditingChange({ ...(editing as DashboardTileDef), config: obj });
                    const errs = validateTile({ ...(editing as DashboardTileDef), config: obj }, computations);
                    setConfigErrors(errs);
                  } catch { 
                    setConfigValid(false); 
                    setConfigErrors([]); 
                  }
                }}
              />
              <Form.Control.Feedback type="invalid">Invalid JSON</Form.Control.Feedback>
              <Form.Text className="text-muted">
                Additional configuration options in JSON format. Common settings:
                <br />• <code>refreshInterval</code>: Refresh interval in milliseconds (default: 30000)
                <br />• <code>autoRefresh</code>: Enable automatic refresh (default: true)
                <br />• <code>cacheSec</code>: Cache duration in seconds
                <br />• <code>columns</code>: Array of column names for table visualization
                <br />• <code>valueField</code>: Field name for stat and timeseries Y-axis values
                <br />• <code>timeField</code>: Time field for timeseries X-axis (default: 'time_start')
                <br />• <code>chartHeight</code>: Height in pixels for timeseries charts (default: 250)
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
        <Button variant="secondary" onClick={handleClose}>Cancel</Button>
        <Button 
          onClick={handleSave} 
          disabled={!editing || !configValid || configErrors.length > 0 || !editing?.name?.trim() || !editing?.computation_id}
        >
          Save
        </Button>
      </Modal.Footer>
    </Modal>
  );
};