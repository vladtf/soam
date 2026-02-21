import React, { useState, useEffect } from 'react';
import { Card, Badge, Spinner, Alert, Button } from 'react-bootstrap';
import { listValueTransformationRules, ValueTransformationRule } from '../api/backendRequests';
import { logger } from '../utils/logger';

const ValueTransformationStatusCard: React.FC = () => {
  const [rules, setRules] = useState<ValueTransformationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      setLoading(true);
      const data = await listValueTransformationRules();
      setRules(data);
      setError(null);
    } catch (err) {
      setError('Failed to load transformation rules');
      logger.error('ValueTransformationStatusCard', 'Failed to load rules', err);
    } finally {
      setLoading(false);
    }
  };

  const getTypeColor = (type: string) => {
    const colors = {
      filter: 'primary',
      aggregate: 'success',
      convert: 'warning',
      validate: 'danger'
    };
    return colors[type as keyof typeof colors] || 'secondary';
  };

  const enabledRules = rules.filter(rule => rule.enabled);
  const totalApplied = rules.reduce((sum, rule) => sum + rule.applied_count, 0);

  if (loading) {
    return (
      <Card>
        <Card.Header>
          <h6 className="mb-0">📊 Value Transformations</h6>
        </Card.Header>
        <Card.Body className="text-center">
          <Spinner animation="border" size="sm" />
        </Card.Body>
      </Card>
    );
  }

  return (
    <Card>
      <Card.Header className="d-flex justify-content-between align-items-center">
        <h6 className="mb-0">📊 Value Transformations</h6>
        <Button
          variant="outline-primary"
          size="sm"
          href="/value-transformations"
        >
          Manage
        </Button>
      </Card.Header>
      <Card.Body>
        {error && (
          <Alert variant="danger" className="py-2">
            {error}
          </Alert>
        )}
        
        <div className="row text-center mb-3">
          <div className="col">
            <div className="h4 mb-0">{rules.length}</div>
            <small className="text-muted">Total Rules</small>
          </div>
          <div className="col">
            <div className="h4 mb-0">{enabledRules.length}</div>
            <small className="text-muted">Enabled</small>
          </div>
          <div className="col">
            <div className="h4 mb-0">{totalApplied.toLocaleString()}</div>
            <small className="text-muted">Applied</small>
          </div>
        </div>

        {rules.length === 0 ? (
          <div className="text-center text-muted py-3">
            <div>No transformation rules configured</div>
            <Button
              variant="primary"
              size="sm"
              href="/value-transformations"
              className="mt-2"
            >
              Create First Rule
            </Button>
          </div>
        ) : (
          <div>
            <h6 className="mb-2">Active Rules by Type:</h6>
            <div className="d-flex flex-wrap gap-2">
              {['filter', 'aggregate', 'convert', 'validate'].map(type => {
                const count = enabledRules.filter(rule => rule.transformation_type === type).length;
                if (count === 0) return null;
                return (
                  <Badge
                    key={type}
                    bg={getTypeColor(type)}
                    className="d-flex align-items-center gap-1"
                  >
                    {type} <span className="badge bg-light text-dark">{count}</span>
                  </Badge>
                );
              })}
            </div>
            
            {rules.length > 3 && (
              <div className="mt-3">
                <h6 className="mb-2">Recent Rules:</h6>
                {rules.slice(0, 3).map(rule => (
                  <div key={rule.id} className="d-flex justify-content-between align-items-center py-1">
                    <div>
                      <code className="small">{rule.field_name}</code>
                      <Badge bg={getTypeColor(rule.transformation_type)} className="ms-2 small">
                        {rule.transformation_type}
                      </Badge>
                    </div>
                    <Badge bg={rule.enabled ? 'success' : 'secondary'} className="small">
                      {rule.applied_count}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default ValueTransformationStatusCard;