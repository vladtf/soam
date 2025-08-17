import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Table, Button, Alert, Spinner, Badge, Modal, Form } from 'react-bootstrap';
import { FaCog, FaUser, FaClock, FaPlus, FaEdit, FaTrash } from 'react-icons/fa';
import { listSettings, deleteSetting, createSetting, type Setting } from '../api/backendRequests';
import { useAuth } from '../context/AuthContext';
import TemperatureThresholdModal from '../components/TemperatureThresholdModal';

const SettingsPage: React.FC = () => {
  const { username } = useAuth();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [showThresholdModal, setShowThresholdModal] = useState<boolean>(false);
  const [showNewSettingModal, setShowNewSettingModal] = useState<boolean>(false);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [deleteKey, setDeleteKey] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [newSettingData, setNewSettingData] = useState({
    key: '',
    value: '',
    value_type: 'string',
    description: '',
    category: ''
  });
  const [savingNewSetting, setSavingNewSetting] = useState<boolean>(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError('');
      const settingsData = await listSettings();
      setSettings(settingsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSetting = (key: string) => {
    setDeleteKey(key);
    setShowDeleteModal(true);
  };

  const confirmDeleteSetting = async () => {
    if (!deleteKey) return;
    setDeleting(true);
    setError('');
    try {
      await deleteSetting(deleteKey);
      setShowDeleteModal(false);
      setDeleteKey(null);
      await loadSettings(); // Refresh the list
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete setting');
    } finally {
      setDeleting(false);
    }
  };

  const handleCreateNewSetting = async () => {
    if (!newSettingData.key.trim() || !newSettingData.value.trim()) {
      setError('Key and value are required');
      return;
    }

    // Basic validation for value types
    if (newSettingData.value_type === 'number') {
      if (isNaN(Number(newSettingData.value))) {
        setError('Value must be a valid number');
        return;
      }
    } else if (newSettingData.value_type === 'boolean') {
      const lowerValue = newSettingData.value.toLowerCase();
      if (!['true', 'false', '1', '0', 'yes', 'no'].includes(lowerValue)) {
        setError('Boolean value must be true/false, 1/0, or yes/no');
        return;
      }
    } else if (newSettingData.value_type === 'json') {
      try {
        JSON.parse(newSettingData.value);
      } catch {
        setError('Value must be valid JSON');
        return;
      }
    }

    setSavingNewSetting(true);
    setError('');

    try {
      await createSetting({
        key: newSettingData.key.trim(),
        value: newSettingData.value.trim(),
        value_type: newSettingData.value_type,
        description: newSettingData.description.trim() || undefined,
        category: newSettingData.category.trim() || undefined,
        created_by: username
      });

      // Reset form and close modal
      setNewSettingData({
        key: '',
        value: '',
        value_type: 'string',
        description: '',
        category: ''
      });
      setShowNewSettingModal(false);
      await loadSettings(); // Refresh the list
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create setting');
    } finally {
      setSavingNewSetting(false);
    }
  };

  const resetNewSettingModal = () => {
    setNewSettingData({
      key: '',
      value: '',
      value_type: 'string',
      description: '',
      category: ''
    });
    setError('');
    setShowNewSettingModal(false);
  };

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'Invalid date';
    }
  };

  const getCategoryBadgeVariant = (category?: string | null) => {
    switch (category) {
      case 'alerts': return 'warning';
      case 'thresholds': return 'info';
      case 'system': return 'secondary';
      default: return 'light';
    }
  };

  return (
    <Container fluid className="py-4">
      <Row className="mb-4">
        <Col>
          <div className="d-flex align-items-center justify-content-between">
            <div>
              <h2 className="mb-1">
                <FaCog className="me-2" />
                Settings Management
              </h2>
              <p className="text-muted">Manage application settings and configurations</p>
            </div>
            <div>
              <Button
                variant="primary"
                onClick={() => setShowThresholdModal(true)}
                className="me-2"
              >
                <FaPlus className="me-1" />
                Configure Temperature Threshold
              </Button>
              <Button
                variant="outline-primary"
                onClick={() => setShowNewSettingModal(true)}
              >
                <FaPlus className="me-1" />
                Add New Setting
              </Button>
            </div>
          </div>
        </Col>
      </Row>

      {error && (
        <Row className="mb-3">
          <Col>
            <Alert variant="danger" dismissible onClose={() => setError('')}>
              {error}
            </Alert>
          </Col>
        </Row>
      )}

      <Row>
        <Col>
          <Card>
            <Card.Header>
              <div className="d-flex align-items-center justify-content-between">
                <h5 className="mb-0">Application Settings</h5>
                <Button variant="outline-primary" size="sm" onClick={loadSettings}>
                  Refresh
                </Button>
              </div>
            </Card.Header>
            <Card.Body className="p-0">
              {loading ? (
                <div className="text-center py-4">
                  <Spinner animation="border" />
                  <div className="mt-2">Loading settings...</div>
                </div>
              ) : settings.length === 0 ? (
                <div className="text-center py-4 text-muted">
                  No settings found. Create your first setting to get started.
                </div>
              ) : (
                <Table responsive striped hover className="mb-0">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th>Value</th>
                      <th>Type</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th><FaUser className="me-1" /> Created By</th>
                      <th><FaUser className="me-1" /> Updated By</th>
                      <th><FaClock className="me-1" /> Created</th>
                      <th><FaClock className="me-1" /> Updated</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settings.map((setting) => (
                      <tr key={setting.id}>
                        <td>
                          <code className="text-primary">{setting.key}</code>
                        </td>
                        <td>
                          <code className="text-dark">
                            {setting.value.length > 50 
                              ? `${setting.value.substring(0, 50)}...`
                              : setting.value
                            }
                          </code>
                        </td>
                        <td>
                          <Badge bg="info" className="text-dark">
                            {setting.value_type || 'string'}
                          </Badge>
                        </td>
                        <td>
                          {setting.category && (
                            <Badge bg={getCategoryBadgeVariant(setting.category)}>
                              {setting.category}
                            </Badge>
                          )}
                        </td>
                        <td>
                          <small className="text-muted">
                            {setting.description || 'No description'}
                          </small>
                        </td>
                        <td>
                          <small className="text-info">
                            <FaUser className="me-1" />
                            {setting.created_by || 'Unknown'}
                          </small>
                        </td>
                        <td>
                          <small className="text-warning">
                            {setting.updated_by ? (
                              <>
                                <FaUser className="me-1" />
                                {setting.updated_by}
                              </>
                            ) : (
                              <span className="text-muted">Never updated</span>
                            )}
                          </small>
                        </td>
                        <td>
                          <small className="text-muted">
                            {formatDateTime(setting.created_at)}
                          </small>
                        </td>
                        <td>
                          <small className="text-muted">
                            {formatDateTime(setting.updated_at)}
                          </small>
                        </td>
                        <td>
                          <div className="btn-group" role="group">
                            {setting.key === 'temperature_threshold' ? (
                              <Button
                                variant="outline-primary"
                                size="sm"
                                onClick={() => setShowThresholdModal(true)}
                                title="Edit Temperature Threshold"
                              >
                                <FaEdit />
                              </Button>
                            ) : (
                              <Button
                                variant="outline-secondary"
                                size="sm"
                                disabled
                                title="No custom editor available"
                              >
                                <FaEdit />
                              </Button>
                            )}
                            <Button
                              variant="outline-danger"
                              size="sm"
                              onClick={() => handleDeleteSetting(setting.key)}
                              title="Delete Setting"
                            >
                              <FaTrash />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <TemperatureThresholdModal
        show={showThresholdModal}
        onHide={() => setShowThresholdModal(false)}
        onUpdate={loadSettings}
      />

      <Modal show={showNewSettingModal} onHide={resetNewSettingModal} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Add New Setting</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && (
            <Alert variant="danger" dismissible onClose={() => setError('')}>
              {error}
            </Alert>
          )}
          
          <Form>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Setting Key <span className="text-danger">*</span></Form.Label>
                  <Form.Control
                    type="text"
                    value={newSettingData.key}
                    onChange={(e) => setNewSettingData(prev => ({ ...prev, key: e.target.value }))}
                    placeholder="e.g., max_temperature_limit"
                    disabled={savingNewSetting}
                  />
                  <Form.Text className="text-muted">
                    Unique identifier for this setting (lowercase, underscores allowed)
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Value Type</Form.Label>
                  <Form.Select
                    value={newSettingData.value_type}
                    onChange={(e) => setNewSettingData(prev => ({ ...prev, value_type: e.target.value }))}
                    disabled={savingNewSetting}
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                    <option value="json">JSON</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3">
              <Form.Label>Setting Value <span className="text-danger">*</span></Form.Label>
              <Form.Control
                type="text"
                value={newSettingData.value}
                onChange={(e) => setNewSettingData(prev => ({ ...prev, value: e.target.value }))}
                placeholder={
                  newSettingData.value_type === 'boolean' ? 'true or false' :
                  newSettingData.value_type === 'number' ? '42 or 3.14' :
                  newSettingData.value_type === 'json' ? '{"key": "value"}' :
                  'Enter the setting value'
                }
                disabled={savingNewSetting}
              />
              {newSettingData.value_type === 'json' && (
                <Form.Text className="text-muted">
                  Enter valid JSON format, e.g., {`{"enabled": true, "timeout": 30}`}
                </Form.Text>
              )}
              {newSettingData.value_type === 'boolean' && (
                <Form.Text className="text-muted">
                  Accepted values: true, false, 1, 0, yes, no (case insensitive)
                </Form.Text>
              )}
              {newSettingData.value_type === 'number' && (
                <Form.Text className="text-muted">
                  Enter a numeric value (integers or decimals)
                </Form.Text>
              )}
            </Form.Group>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Category</Form.Label>
                  <Form.Control
                    type="text"
                    value={newSettingData.category}
                    onChange={(e) => setNewSettingData(prev => ({ ...prev, category: e.target.value }))}
                    placeholder="e.g., alerts, thresholds, system"
                    disabled={savingNewSetting}
                  />
                  <Form.Text className="text-muted">
                    Optional category for grouping settings
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Description</Form.Label>
                  <Form.Control
                    as="textarea"
                    rows={3}
                    value={newSettingData.description}
                    onChange={(e) => setNewSettingData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe what this setting does..."
                    disabled={savingNewSetting}
                  />
                </Form.Group>
              </Col>
            </Row>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={resetNewSettingModal} disabled={savingNewSetting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleCreateNewSetting} disabled={savingNewSetting}>
            {savingNewSetting ? (
              <>
                <Spinner animation="border" size="sm" className="me-2" />
                Creating...
              </>
            ) : (
              <>
                <FaPlus className="me-1" />
                Create Setting
              </>
            )}
          </Button>
        </Modal.Footer>
      </Modal>
      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Confirm Delete</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          Are you sure you want to delete the setting{' '}
          <code>{deleteKey}</code>?
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={confirmDeleteSetting} disabled={deleting}>
            {deleting ? (
              <>
                <Spinner animation="border" size="sm" className="me-2" />
                Deleting...
              </>
            ) : (
              'Delete'
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default SettingsPage;
