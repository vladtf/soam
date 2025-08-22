import React from 'react';
import { Button, Card, Alert } from 'react-bootstrap';
import { FaBug, FaExclamationTriangle } from 'react-icons/fa';
import { withErrorBoundary } from './withErrorBoundary';
import { useComponentErrorHandler } from '../utils/devTools';

const ErrorTestComponent: React.FC = () => {
  const { handleError, wrapAction } = useComponentErrorHandler('ErrorTestComponent');

  const throwSyncError = () => {
    throw new Error('This is a test synchronous error with detailed stack trace');
  };

  const throwAsyncError = async () => {
    await new Promise(resolve => setTimeout(resolve, 100));
    throw new Error('This is a test asynchronous error');
  };

  const throwNetworkError = async () => {
    try {
      await fetch('/non-existent-endpoint');
    } catch (error) {
      handleError(error as Error, 'network_test');
      throw error;
    }
  };

  const throwCustomError = () => {
    const error = new Error('Custom error with additional context');
    (error as any).customProperty = 'test-value';
    (error as any).errorCode = 'TEST_ERROR_001';
    throw error;
  };

  const triggerComponentError = () => {
    // This will be caught by the error boundary
    throw new Error('Component-level error that should show the dev overlay');
  };

  // Only show in development
  if ((import.meta as any).env?.MODE !== 'development') {
    return null;
  }

  return (
    <Card className="mt-3">
      <Card.Header className="bg-warning text-dark">
        <FaExclamationTriangle className="me-2" />
        Development Error Testing
      </Card.Header>
      <Card.Body>
        <Alert variant="info" className="mb-3">
          <strong>Development Only:</strong> These buttons are for testing the error handling system.
          Try them to see how errors are captured and displayed.
        </Alert>
        
        <div className="d-flex flex-wrap gap-2">
          <Button
            variant="outline-danger"
            size="sm"
            onClick={wrapAction('sync_error_test', throwSyncError)}
          >
            <FaBug className="me-1" />
            Sync Error
          </Button>
          
          <Button
            variant="outline-danger"
            size="sm"
            onClick={wrapAction('async_error_test', throwAsyncError)}
          >
            <FaBug className="me-1" />
            Async Error
          </Button>
          
          <Button
            variant="outline-danger"
            size="sm"
            onClick={wrapAction('network_error_test', throwNetworkError)}
          >
            <FaBug className="me-1" />
            Network Error
          </Button>
          
          <Button
            variant="outline-danger"
            size="sm"
            onClick={wrapAction('custom_error_test', throwCustomError)}
          >
            <FaBug className="me-1" />
            Custom Error
          </Button>
          
          <Button
            variant="danger"
            size="sm"
            onClick={triggerComponentError}
          >
            <FaExclamationTriangle className="me-1" />
            Component Error
          </Button>
        </div>

        <div className="mt-3">
          <small className="text-muted">
            💡 <strong>Tip:</strong> Press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> to open the debug panel,
            or click the floating debug button in the bottom-right corner.
          </small>
        </div>
      </Card.Body>
    </Card>
  );
};

export default withErrorBoundary(ErrorTestComponent, {
  componentName: 'ErrorTestComponent',
  showDevOverlay: true,
});
