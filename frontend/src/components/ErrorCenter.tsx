import React from 'react';
import { Modal, Button, Table, Badge } from 'react-bootstrap';

export type ErrorRecord = {
  id: number;
  message: string;
  severity?: 'debug' | 'info' | 'warn' | 'error' | 'fatal';
  component?: string;
  context?: string;
  url?: string;
  time: Date;
};

interface ErrorCenterProps {
  show: boolean;
  errors: ErrorRecord[];
  onClose: () => void;
  onClear: () => void;
}

const ErrorCenter: React.FC<ErrorCenterProps> = ({ show, errors, onClose, onClear }) => {
  const copyToClipboard = async (text: string) => {
    try { await navigator.clipboard.writeText(text); } catch { /* ignore */ }
  };

  return (
    <Modal show={show} onHide={onClose} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Errors</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="d-flex justify-content-between align-items-center mb-2">
          <div className="text-body-secondary small">Most recent first</div>
          <Button variant="outline-danger" size="sm" onClick={onClear} disabled={errors.length === 0}>Clear</Button>
        </div>
        <div className="table-responsive">
          <Table hover size="sm" className="mb-0">
            <thead>
              <tr>
                <th>When</th>
                <th>Severity</th>
                <th>Component</th>
                <th>Context</th>
                <th>Message</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {errors.map((e) => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{e.time.toLocaleString()}</td>
                  <td>
                    <Badge bg={e.severity === 'fatal' || e.severity === 'error' ? 'danger' : (e.severity === 'warn' ? 'warning' : 'secondary')}>
                      {e.severity || 'error'}
                    </Badge>
                  </td>
                  <td>{e.component || '-'}</td>
                  <td>{e.context || '-'}</td>
                  <td style={{ maxWidth: 380, overflow: 'hidden', textOverflow: 'ellipsis' }} title={e.message}>{e.message}</td>
                  <td className="text-end">
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      onClick={() => copyToClipboard(`${e.time.toISOString()} [${e.severity || 'error'}] ${e.component || ''} ${e.context || ''} - ${e.message}`)}
                    >Copy</Button>
                  </td>
                </tr>
              ))}
              {errors.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center text-body-secondary py-3">No errors</td>
                </tr>
              )}
            </tbody>
          </Table>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>Close</Button>
      </Modal.Footer>
    </Modal>
  );
};

export default ErrorCenter;


