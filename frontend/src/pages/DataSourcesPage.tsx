import React, { useState, useEffect, useMemo } from 'react';
import { 
  Container, 
  Row, 
  Col, 
  Card, 
  Button, 
  Table, 
  Badge, 
  Modal, 
  Alert, 
  Spinner,
  Form
} from 'react-bootstrap';
import { 
  fetchDataSources, 
  fetchDataSourceTypes,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  startDataSource,
  stopDataSource,
  restartDataSource,
  getDataSourceHealth,
  getConnectorStatusOverview
} from '../api/backendRequests';
import { 
  DataSource, 
  DataSourceType, 
  CreateDataSourceRequest,
  UpdateDataSourceRequest,
  DataSourceHealth,
  ConnectorStatusOverview
} from '../types/dataSource';
import DynamicConfigForm from '../components/DynamicConfigForm';

const DataSourcesPage: React.FC = () => {
  // State management
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [dataSourceTypes, setDataSourceTypes] = useState<DataSourceType[]>([]);
  const [statusOverview, setStatusOverview] = useState<ConnectorStatusOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showHealthModal, setShowHealthModal] = useState(false);
  
  // Selected items
  const [selectedSource, setSelectedSource] = useState<DataSource | null>(null);
  const [selectedHealth, setSelectedHealth] = useState<DataSourceHealth | null>(null);
  
  // Form states
  const [createForm, setCreateForm] = useState<CreateDataSourceRequest>({
    name: '',
    type_name: '',
    config: {},
    enabled: true
  });
  const [editForm, setEditForm] = useState<UpdateDataSourceRequest>({});

  // Load data on component mount
  useEffect(() => {
    loadDataSources();
    loadDataSourceTypes();
    loadStatusOverview();
    
    // Set up periodic refresh for status
    const interval = setInterval(loadStatusOverview, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDataSources = async () => {
    try {
      const sources = await fetchDataSources(false); // Include disabled sources
      setDataSources(sources);
      setError(null);
    } catch (err) {
      console.error('Failed to load data sources:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data sources');
    }
  };

  const loadDataSourceTypes = async () => {
    try {
      const types = await fetchDataSourceTypes();
      setDataSourceTypes(types);
    } catch (err) {
      console.error('Failed to load data source types:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data source types');
    } finally {
      setLoading(false);
    }
  };

  const loadStatusOverview = async () => {
    try {
      const overview = await getConnectorStatusOverview();
      setStatusOverview(overview);
    } catch (err) {
      console.error('Failed to load status overview:', err);
      // Don't set error for status overview failures
    }
  };

  const handleCreateSource = async () => {
    try {
      await createDataSource(createForm);
      setShowCreateModal(false);
      setCreateForm({ name: '', type_name: '', config: {}, enabled: true });
      await loadDataSources();
    } catch (err) {
      console.error('Failed to create data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to create data source');
    }
  };

  const handleEditSource = async () => {
    if (!selectedSource) return;
    
    try {
      await updateDataSource(selectedSource.id, editForm);
      setShowEditModal(false);
      setEditForm({});
      setSelectedSource(null);
      await loadDataSources();
    } catch (err) {
      console.error('Failed to update data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to update data source');
    }
  };

  const handleDeleteSource = async () => {
    if (!selectedSource) return;
    
    try {
      await deleteDataSource(selectedSource.id);
      setShowDeleteModal(false);
      setSelectedSource(null);
      await loadDataSources();
    } catch (err) {
      console.error('Failed to delete data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete data source');
    }
  };

  const handleStartSource = async (source: DataSource) => {
    try {
      await startDataSource(source.id);
      await loadDataSources();
      await loadStatusOverview();
    } catch (err) {
      console.error('Failed to start data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to start data source');
    }
  };

  const handleStopSource = async (source: DataSource) => {
    try {
      await stopDataSource(source.id);
      await loadDataSources();
      await loadStatusOverview();
    } catch (err) {
      console.error('Failed to stop data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to stop data source');
    }
  };

  const handleRestartSource = async (source: DataSource) => {
    try {
      await restartDataSource(source.id);
      await loadDataSources();
      await loadStatusOverview();
    } catch (err) {
      console.error('Failed to restart data source:', err);
      setError(err instanceof Error ? err.message : 'Failed to restart data source');
    }
  };

  const handleShowHealth = async (source: DataSource) => {
    try {
      const health = await getDataSourceHealth(source.id);
      setSelectedHealth(health);
      setSelectedSource(source);
      setShowHealthModal(true);
    } catch (err) {
      console.error('Failed to get health status:', err);
      setError(err instanceof Error ? err.message : 'Failed to get health status');
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      'active': 'success',
      'connecting': 'warning',
      'inactive': 'secondary',
      'error': 'danger',
      'stopped': 'dark'
    };
    return <Badge bg={variants[status] || 'secondary'}>{status.toUpperCase()}</Badge>;
  };

  const getSelectedSourceType = useMemo(() => {
    return dataSourceTypes.find(type => type.name === createForm.type_name);
  }, [createForm.type_name, dataSourceTypes]);

  if (loading) {
    return (
      <Container className="mt-4">
        <div className="text-center">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
          <p className="mt-2">Loading data sources...</p>
        </div>
      </Container>
    );
  }

  return (
    <Container className="pt-3 pb-4">
      <Row className="mb-4">
        <Col>
          <h1 className="mb-3">
            🔌 Data Sources Management
          </h1>
          <p className="text-muted">
            Manage and monitor your data ingestion sources. Connect to MQTT brokers, REST APIs, and other data sources.
          </p>
        </Col>
      </Row>

      {error && (
        <Row className="mb-4">
          <Col>
            <Alert variant="danger" dismissible onClose={() => setError(null)}>
              <Alert.Heading>Error</Alert.Heading>
              {error}
            </Alert>
          </Col>
        </Row>
      )}

      {/* Status Overview */}
      <Row className="mb-4">
        <Col md={3}>
          <Card className="h-100">
            <Card.Body>
              <Card.Title className="d-flex align-items-center">
                📊 Overview
              </Card.Title>
              <div className="mt-3">
                <div className="mb-2">
                  <strong>Total Sources:</strong> {dataSources.length}
                </div>
                <div className="mb-2">
                  <strong>Active:</strong> {dataSources.filter(s => s.status === 'active').length}
                </div>
                <div className="mb-2">
                  <strong>Connected:</strong> {statusOverview?.active_connectors || 0}
                </div>
                <div>
                  <strong>Available Types:</strong> {dataSourceTypes.length}
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={9}>
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <Card.Title>📋 Data Sources</Card.Title>
                <Button 
                  variant="primary" 
                  onClick={() => setShowCreateModal(true)}
                  disabled={dataSourceTypes.length === 0}
                >
                  ➕ Add New Source
                </Button>
              </div>

              <Table responsive striped hover>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Ingestion ID</th>
                    <th>Last Connection</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {dataSources.map((source) => (
                    <tr key={source.id}>
                      <td>
                        <div>
                          <strong>{source.name}</strong>
                          {!source.enabled && (
                            <Badge bg="secondary" className="ms-2">Disabled</Badge>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="d-flex align-items-center">
                          {dataSourceTypes.find(t => t.name === source.type_name)?.icon || '🔗'}
                          <span className="ms-2">{source.type_display_name}</span>
                        </div>
                      </td>
                      <td>{getStatusBadge(source.status)}</td>
                      <td>
                        <code className="small">{source.ingestion_id}</code>
                      </td>
                      <td>
                        {source.last_connection ? (
                          new Date(source.last_connection).toLocaleString()
                        ) : (
                          <span className="text-muted">Never</span>
                        )}
                      </td>
                      <td>
                        <div className="btn-group" role="group">
                          {source.status === 'active' ? (
                            <>
                              <Button
                                size="sm"
                                variant="outline-warning"
                                onClick={() => handleStopSource(source)}
                                title="Stop"
                              >
                                🛑
                              </Button>
                              <Button
                                size="sm"
                                variant="outline-primary"
                                onClick={() => handleRestartSource(source)}
                                title="Restart"
                              >
                                🔄
                              </Button>
                            </>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline-success"
                              onClick={() => handleStartSource(source)}
                              title="Start"
                              disabled={!source.enabled}
                            >
                              ▶️
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline-info"
                            onClick={() => handleShowHealth(source)}
                            title="Health Check"
                          >
                            🩺
                          </Button>
                          <Button
                            size="sm"
                            variant="outline-secondary"
                            onClick={() => {
                              setSelectedSource(source);
                              setEditForm({
                                name: source.name,
                                config: source.config,
                                enabled: source.enabled
                              });
                              setShowEditModal(true);
                            }}
                            title="Edit"
                          >
                            ✏️
                          </Button>
                          <Button
                            size="sm"
                            variant="outline-danger"
                            onClick={() => {
                              setSelectedSource(source);
                              setShowDeleteModal(true);
                            }}
                            title="Delete"
                          >
                            🗑️
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {dataSources.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center text-muted py-4">
                        No data sources configured yet. Create your first data source to get started!
                      </td>
                    </tr>
                  )}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Create Data Source Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>➕ Create New Data Source</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Name</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="Enter data source name"
                    value={createForm.name}
                    onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Type</Form.Label>
                  <Form.Select
                    value={createForm.type_name}
                    onChange={(e) => setCreateForm({ ...createForm, type_name: e.target.value, config: {} })}
                  >
                    <option value="">Select data source type...</option>
                    {dataSourceTypes.map((type) => (
                      <option key={type.id} value={type.name}>
                        {type.icon} {type.display_name}
                      </option>
                    ))}
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                label="Enable after creation"
                checked={createForm.enabled}
                onChange={(e) => setCreateForm({ ...createForm, enabled: e.target.checked })}
              />
            </Form.Group>

            {getSelectedSourceType && (
              <div>
                <h6>Configuration</h6>
                <DynamicConfigForm
                  schema={getSelectedSourceType.config_schema}
                  value={createForm.config}
                  onChange={(config: any) => setCreateForm({ ...createForm, config })}
                />
              </div>
            )}
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleCreateSource}
            disabled={!createForm.name || !createForm.type_name}
          >
            Create Data Source
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Edit Data Source Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>✏️ Edit Data Source</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedSource && (
            <Form>
              <Form.Group className="mb-3">
                <Form.Label>Name</Form.Label>
                <Form.Control
                  type="text"
                  value={editForm.name || ''}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Check
                  type="checkbox"
                  label="Enabled"
                  checked={editForm.enabled ?? true}
                  onChange={(e) => setEditForm({ ...editForm, enabled: e.target.checked })}
                />
              </Form.Group>

              <div>
                <h6>Configuration</h6>
                <p className="text-muted small">
                  Type: {selectedSource.type_display_name} ({selectedSource.type_name})
                </p>
                {/* TODO: Add dynamic config form for editing */}
                <Alert variant="info">
                  Configuration editing coming soon. For now, delete and recreate the source with new settings.
                </Alert>
              </div>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEditModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleEditSource}>
            Update Data Source
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>🗑️ Delete Data Source</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedSource && (
            <div>
              <p>Are you sure you want to delete the data source <strong>"{selectedSource.name}"</strong>?</p>
              <Alert variant="warning">
                <Alert.Heading>Warning</Alert.Heading>
                This action cannot be undone. The data source will be permanently removed and any active connections will be stopped.
              </Alert>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDeleteSource}>
            Delete Data Source
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Health Check Modal */}
      <Modal show={showHealthModal} onHide={() => setShowHealthModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>🩺 Health Check Results</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedSource && selectedHealth && (
            <div>
              <h6>{selectedSource.name} ({selectedSource.type_display_name})</h6>
              
              <Row className="mt-3">
                <Col md={6}>
                  <Card>
                    <Card.Body>
                      <Card.Title className="h6">Status</Card.Title>
                      <div className="mb-2">
                        <strong>Overall:</strong> {getStatusBadge(selectedHealth.status)}
                      </div>
                      <div className="mb-2">
                        <strong>Healthy:</strong> {
                          selectedHealth.healthy ? (
                            <Badge bg="success">Yes</Badge>
                          ) : (
                            <Badge bg="danger">No</Badge>
                          )
                        }
                      </div>
                      {selectedHealth.running !== undefined && (
                        <div>
                          <strong>Running:</strong> {
                            selectedHealth.running ? (
                              <Badge bg="success">Yes</Badge>
                            ) : (
                              <Badge bg="warning">No</Badge>
                            )
                          }
                        </div>
                      )}
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={6}>
                  <Card>
                    <Card.Body>
                      <Card.Title className="h6">Connection Details</Card.Title>
                      {selectedHealth.connected !== undefined && (
                        <div className="mb-2">
                          <strong>Connected:</strong> {selectedHealth.connected ? 'Yes' : 'No'}
                        </div>
                      )}
                      {selectedHealth.endpoint && (
                        <div className="mb-2">
                          <strong>Endpoint:</strong> <code>{selectedHealth.endpoint}</code>
                        </div>
                      )}
                      {selectedHealth.broker && (
                        <div className="mb-2">
                          <strong>Broker:</strong> <code>{selectedHealth.broker}:{selectedHealth.port}</code>
                        </div>
                      )}
                      {selectedHealth.topics && (
                        <div>
                          <strong>Topics:</strong>
                          <ul className="mb-0 mt-1">
                            {selectedHealth.topics.map((topic, index) => (
                              <li key={index}><code>{topic}</code></li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              {selectedHealth.error && (
                <Alert variant="danger" className="mt-3">
                  <Alert.Heading>Error</Alert.Heading>
                  {selectedHealth.error}
                </Alert>
              )}

              {selectedHealth.message && !selectedHealth.error && (
                <Alert variant="info" className="mt-3">
                  {selectedHealth.message}
                </Alert>
              )}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowHealthModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default DataSourcesPage;
