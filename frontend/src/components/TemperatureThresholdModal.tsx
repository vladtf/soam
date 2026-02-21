import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Alert, Spinner } from 'react-bootstrap';
import { getSetting, updateSetting, createSetting } from '../api/backendRequests';
import { useAuth } from '../context/AuthContext';
import { logger } from '../utils/logger';

interface TemperatureThresholdModalProps {
  show: boolean;
  onHide: () => void;
  onUpdate?: () => void;
}

const TemperatureThresholdModal: React.FC<TemperatureThresholdModalProps> = ({ show, onHide, onUpdate }) => {
  const { username } = useAuth();
  const [threshold, setThreshold] = useState<number>(30.0);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<boolean>(false);

  // Load current threshold when modal opens
  useEffect(() => {
    if (show) {
      loadCurrentThreshold();
      setError('');
      setSuccess(false);
    }
  }, [show]);

  const loadCurrentThreshold = async () => {
    setLoading(true);
    try {
      const setting = await getSetting('temperature_threshold');
      const thresholdValue = parseFloat(setting.value);
      setThreshold(thresholdValue);
      logger.debug('TemperatureThreshold', `Current threshold: ${thresholdValue}°C`);
    } catch {
      logger.debug('TemperatureThreshold', 'Setting not found, using default 30°C');
      setThreshold(30.0);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (threshold < 0 || threshold > 100) {
      setError('Temperature threshold must be between 0 and 100°C');
      return;
    }

    setSaving(true);
    setError('');

    try {
      // Check if the setting exists first
      let settingExists = false;
      try {
        await getSetting('temperature_threshold');
        settingExists = true;
      } catch {
        settingExists = false;
      }

      if (settingExists) {
        await updateSetting('temperature_threshold', {
          value: threshold.toString(),
          value_type: 'number',
          description: 'Temperature threshold for alerts in Celsius',
          category: 'alerts',
          updated_by: username
        });
      } else {
        await createSetting({
          key: 'temperature_threshold',
          value: threshold.toString(),
          value_type: 'number',
          description: 'Temperature threshold for alerts in Celsius',
          category: 'alerts',
          created_by: username
        });
      }

      setSuccess(true);
      if (onUpdate) {
        onUpdate();
      }

      // Close modal after a short delay to show success message
      setTimeout(() => {
        onHide();
        setSuccess(false);
      }, 1500);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update temperature threshold');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    setError('');
    setSuccess(false);
    onHide();
  };

  return (
    <Modal show={show} onHide={handleClose} centered>
      <Modal.Header closeButton>
        <Modal.Title>Configure Temperature Alert Threshold</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && (
          <Alert variant="danger" dismissible onClose={() => setError('')}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert variant="success">
            Temperature threshold updated successfully!
          </Alert>
        )}
        
        {loading ? (
          <div className="text-center py-3">
            <Spinner animation="border" size="sm" className="me-2" />
            Loading current threshold...
          </div>
        ) : (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Temperature Threshold (°C)</Form.Label>
              <Form.Control
                type="number"
                value={threshold}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value === '') return;
                  const num = parseFloat(value);
                  if (!isNaN(num)) setThreshold(num);
                }}
                min="0"
                max="100"
                step="0.1"
                placeholder="Enter temperature threshold"
                disabled={saving}
              />
              <Form.Text className="text-muted">
                Sensors reporting temperatures above this threshold will trigger alerts.
                Valid range: 0-100°C
              </Form.Text>
            </Form.Group>
          </Form>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={handleClose} disabled={saving}>
          Cancel
        </Button>
        <Button 
          variant="primary" 
          onClick={handleSave} 
          disabled={loading || saving}
        >
          {saving ? (
            <>
              <Spinner animation="border" size="sm" className="me-2" />
              Saving...
            </>
          ) : (
            'Save Changes'
          )}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default TemperatureThresholdModal;
