import React from 'react';
import { Modal, Spinner } from 'react-bootstrap';

interface Props {
  open: boolean;
  loading: boolean;
  data: unknown[] | null;
  onClose: () => void;
}

const PreviewModal: React.FC<Props> = ({ open, loading, data, onClose }) => {
  return (
    <Modal show={open} onHide={onClose} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Preview</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {loading ? (
          <div className="d-flex align-items-center gap-2">
            <Spinner animation="border" size="sm" />
            <span>Loading preview…</span>
          </div>
        ) : (
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(data, null, 2)}</pre>
        )}
      </Modal.Body>
    </Modal>
  );
};

export default PreviewModal;
