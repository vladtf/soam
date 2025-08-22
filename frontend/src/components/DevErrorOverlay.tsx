import React, { useState } from 'react';
import { Button, Card, Badge } from 'react-bootstrap';
import { FaBug, FaCode, FaCopy, FaExclamationTriangle, FaRedo, FaTimes, FaDownload } from 'react-icons/fa';

export interface DevErrorInfo {
  error: Error;
  errorInfo?: React.ErrorInfo;
  componentStack?: string;
  errorBoundary?: string;
  url?: string;
  userAgent?: string;
  timestamp: Date;
  buildInfo?: {
    mode: string;
    commit?: string;
    version?: string;
  };
  context?: Record<string, unknown>;
}

interface DevErrorOverlayProps {
  errorInfo: DevErrorInfo;
  onDismiss: () => void;
  onRetry?: () => void;
}

const DevErrorOverlay: React.FC<DevErrorOverlayProps> = ({ errorInfo, onDismiss, onRetry }) => {
  const [minimized, setMinimized] = useState(false);
  const [activeTab, setActiveTab] = useState<'error' | 'stack' | 'component' | 'context'>('error');

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  const downloadErrorReport = () => {
    const report = {
      error: {
        name: errorInfo.error.name,
        message: errorInfo.error.message,
        stack: errorInfo.error.stack,
      },
      errorInfo: errorInfo.errorInfo,
      componentStack: errorInfo.componentStack,
      url: errorInfo.url,
      userAgent: errorInfo.userAgent,
      timestamp: errorInfo.timestamp.toISOString(),
      buildInfo: errorInfo.buildInfo,
      context: errorInfo.context,
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `error-report-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatStackTrace = (stack?: string) => {
    if (!stack) return null;
    
    return stack
      .split('\n')
      .map((line, index) => {
        const isMainError = index === 0;
        const isSourceCode = line.includes('webpack://') || line.includes('.tsx') || line.includes('.ts');
        const isNodeModules = line.includes('node_modules');
        
        let className = 'text-muted';
        if (isMainError) className = 'text-danger fw-bold';
        else if (isSourceCode) className = 'text-primary';
        else if (isNodeModules) className = 'text-secondary';
        
        return (
          <div key={index} className={className} style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>
            {line}
          </div>
        );
      });
  };

  const renderMinimized = () => (
    <div 
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: 9999,
        backgroundColor: '#dc3545',
        color: 'white',
        padding: '10px 15px',
        borderRadius: '8px',
        cursor: 'pointer',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}
      onClick={() => setMinimized(false)}
    >
      <FaBug />
      <span>Error Detected</span>
      <Badge bg="light" text="dark">{errorInfo.error.name}</Badge>
    </div>
  );

  if (minimized) {
    return renderMinimized();
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 10000,
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          width: '90%',
          maxWidth: '1000px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 10px 40px rgba(0,0,0,0.3)',
        }}
      >
        {/* Header */}
        <div
          style={{
            backgroundColor: '#dc3545',
            color: 'white',
            padding: '15px 20px',
            borderRadius: '12px 12px 0 0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FaExclamationTriangle size={20} />
            <div>
              <h5 style={{ margin: 0 }}>Development Error</h5>
              <small style={{ opacity: 0.9 }}>
                {errorInfo.timestamp.toLocaleString()} • {errorInfo.buildInfo?.mode || 'development'}
              </small>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              size="sm"
              variant="light"
              onClick={() => setMinimized(true)}
              title="Minimize"
            >
              <FaTimes />
            </Button>
          </div>
        </div>

        {/* Error Summary */}
        <div style={{ padding: '20px', borderBottom: '1px solid #dee2e6' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <Badge bg="danger">{errorInfo.error.name}</Badge>
            {errorInfo.url && (
              <Badge bg="secondary" title={errorInfo.url}>
                {new URL(errorInfo.url).pathname}
              </Badge>
            )}
          </div>
          <h6 style={{ color: '#dc3545', marginBottom: '15px', fontSize: '1.1rem' }}>
            {errorInfo.error.message}
          </h6>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Button size="sm" variant="danger" onClick={onDismiss}>
              <FaTimes className="me-1" />
              Dismiss
            </Button>
            {onRetry && (
              <Button size="sm" variant="outline-primary" onClick={onRetry}>
                <FaRedo className="me-1" />
                Retry
              </Button>
            )}
            <Button
              size="sm"
              variant="outline-secondary"
              onClick={() => copyToClipboard(errorInfo.error.stack || errorInfo.error.message)}
            >
              <FaCopy className="me-1" />
              Copy Error
            </Button>
            <Button size="sm" variant="outline-secondary" onClick={downloadErrorReport}>
              <FaDownload className="me-1" />
              Download Report
            </Button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ padding: '0 20px', borderBottom: '1px solid #dee2e6' }}>
          <div style={{ display: 'flex', gap: '0' }}>
            {[
              { key: 'error' as const, label: 'Stack Trace', icon: <FaBug /> },
              { key: 'component' as const, label: 'Component Stack', icon: <FaCode /> },
              { key: 'context' as const, label: 'Context', icon: <FaCode /> },
            ].map(tab => (
              <button
                key={tab.key}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderBottom: activeTab === tab.key ? '2px solid #0d6efd' : '2px solid transparent',
                  color: activeTab === tab.key ? '#0d6efd' : '#6c757d',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        <div style={{ flex: 1, padding: '20px', overflow: 'auto' }}>
          {activeTab === 'error' && (
            <div>
              <h6 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FaBug />
                Stack Trace
                <Button
                  size="sm"
                  variant="outline-secondary"
                  onClick={() => copyToClipboard(errorInfo.error.stack || '')}
                >
                  <FaCopy />
                </Button>
              </h6>
              <div
                style={{
                  backgroundColor: '#f8f9fa',
                  padding: '15px',
                  borderRadius: '8px',
                  border: '1px solid #dee2e6',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  lineHeight: '1.4',
                  overflow: 'auto',
                }}
              >
                {formatStackTrace(errorInfo.error.stack)}
              </div>
            </div>
          )}

          {activeTab === 'component' && (
            <div>
              <h6 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FaCode />
                Component Stack
                <Button
                  size="sm"
                  variant="outline-secondary"
                  onClick={() => copyToClipboard(errorInfo.componentStack || errorInfo.errorInfo?.componentStack || '')}
                >
                  <FaCopy />
                </Button>
              </h6>
              <div
                style={{
                  backgroundColor: '#f8f9fa',
                  padding: '15px',
                  borderRadius: '8px',
                  border: '1px solid #dee2e6',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {errorInfo.componentStack || errorInfo.errorInfo?.componentStack || 'No component stack available'}
              </div>
            </div>
          )}

          {activeTab === 'context' && (
            <div>
              <h6 style={{ marginBottom: '15px' }}>Debug Context</h6>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {/* Build Info */}
                {errorInfo.buildInfo && (
                  <Card>
                    <Card.Header style={{ padding: '8px 12px', fontSize: '0.9rem' }}>
                      Build Information
                    </Card.Header>
                    <Card.Body style={{ padding: '12px' }}>
                      <div style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>
                        <div><strong>Mode:</strong> {errorInfo.buildInfo.mode}</div>
                        {errorInfo.buildInfo.version && <div><strong>Version:</strong> {errorInfo.buildInfo.version}</div>}
                        {errorInfo.buildInfo.commit && <div><strong>Commit:</strong> {errorInfo.buildInfo.commit}</div>}
                      </div>
                    </Card.Body>
                  </Card>
                )}

                {/* Additional Context */}
                {errorInfo.context && Object.keys(errorInfo.context).length > 0 && (
                  <Card>
                    <Card.Header style={{ padding: '8px 12px', fontSize: '0.9rem' }}>
                      Additional Context
                    </Card.Header>
                    <Card.Body style={{ padding: '12px' }}>
                      <pre style={{ fontSize: '0.85rem', margin: 0 }}>
                        {JSON.stringify(errorInfo.context, null, 2)}
                      </pre>
                    </Card.Body>
                  </Card>
                )}

                {/* Environment */}
                <Card>
                  <Card.Header style={{ padding: '8px 12px', fontSize: '0.9rem' }}>
                    Environment
                  </Card.Header>
                  <Card.Body style={{ padding: '12px' }}>
                    <div style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>
                      <div><strong>URL:</strong> {errorInfo.url || window.location.href}</div>
                      <div><strong>User Agent:</strong> {errorInfo.userAgent || navigator.userAgent}</div>
                      <div><strong>Viewport:</strong> {window.innerWidth}x{window.innerHeight}</div>
                      <div><strong>Timestamp:</strong> {errorInfo.timestamp.toISOString()}</div>
                    </div>
                  </Card.Body>
                </Card>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DevErrorOverlay;
