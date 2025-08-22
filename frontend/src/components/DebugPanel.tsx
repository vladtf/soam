import React, { useState, useEffect } from 'react';
import { Modal, Button, Card, Badge, Accordion, Form, InputGroup } from 'react-bootstrap';
import { FaBug, FaCopy, FaTrash, FaDownload, FaFilter } from 'react-icons/fa';
import { useError } from '../context/ErrorContext';
import { useNetworkErrorHandler } from '../utils/networkErrorHandler';

interface DebugPanelProps {
  show: boolean;
  onHide: () => void;
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'network';
type LogEntry = {
  id: string;
  level: LogLevel;
  message: string;
  timestamp: Date;
  source?: string;
  details?: any;
  stack?: string;
};

const DebugPanel: React.FC<DebugPanelProps> = ({ show, onHide }) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const { error } = useError();
  const { errors: networkErrors, clearErrors: clearNetworkErrors } = useNetworkErrorHandler();

  // Capture console logs in development
  useEffect(() => {
    if ((import.meta as any).env?.MODE !== 'development') return;

    const originalConsole = {
      log: console.log,
      warn: console.warn,
      error: console.error,
      debug: console.debug,
      info: console.info,
    };

    const createLogCapture = (level: LogLevel, originalFn: (...args: any[]) => void) => {
      return (...args: any[]) => {
        originalFn(...args);
        
        const logEntry: LogEntry = {
          id: `${Date.now()}-${Math.random()}`,
          level,
          message: args.map(arg => typeof arg === 'string' ? arg : JSON.stringify(arg, null, 2)).join(' '),
          timestamp: new Date(),
          source: 'console',
          details: args.length > 1 ? args.slice(1) : undefined,
        };

        setLogs(prev => [logEntry, ...prev.slice(0, 499)]); // Keep last 500 logs
      };
    };

    // Override console methods
    console.log = createLogCapture('debug', originalConsole.log);
    console.info = createLogCapture('info', originalConsole.info);
    console.warn = createLogCapture('warn', originalConsole.warn);
    console.error = createLogCapture('error', originalConsole.error);
    console.debug = createLogCapture('debug', originalConsole.debug);

    return () => {
      // Restore original console methods
      Object.assign(console, originalConsole);
    };
  }, []);

  // Add error context logs
  useEffect(() => {
    if (error) {
      const errorLog: LogEntry = {
        id: `error-${Date.now()}`,
        level: 'error',
        message: error,
        timestamp: new Date(),
        source: 'ErrorContext',
      };
      setLogs(prev => [errorLog, ...prev]);
    }
  }, [error]);

  // Add network error logs
  useEffect(() => {
    networkErrors.forEach(networkError => {
      const networkLog: LogEntry = {
        id: `network-${networkError.timestamp.getTime()}`,
        level: 'network',
        message: `${networkError.request.method} ${networkError.request.url} - ${networkError.response?.status || 'Failed'}`,
        timestamp: networkError.timestamp,
        source: 'Network',
        details: networkError,
        stack: networkError.error.stack,
      };
      
      setLogs(prev => {
        // Avoid duplicates
        if (prev.some(log => log.id === networkLog.id)) return prev;
        return [networkLog, ...prev];
      });
    });
  }, [networkErrors]);

  const filteredLogs = logs.filter(log => {
    if (filter !== 'all' && log.level !== filter) return false;
    if (searchTerm && !log.message.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const clearLogs = () => {
    setLogs([]);
    clearNetworkErrors();
  };

  const copyLogs = () => {
    const logData = filteredLogs.map(log => ({
      timestamp: log.timestamp.toISOString(),
      level: log.level,
      source: log.source,
      message: log.message,
      details: log.details,
      stack: log.stack,
    }));
    
    navigator.clipboard?.writeText(JSON.stringify(logData, null, 2));
  };

  const downloadLogs = () => {
    const logData = filteredLogs.map(log => ({
      timestamp: log.timestamp.toISOString(),
      level: log.level,
      source: log.source,
      message: log.message,
      details: log.details,
      stack: log.stack,
    }));
    
    const blob = new Blob([JSON.stringify(logData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `debug-logs-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getLevelBadgeVariant = (level: LogLevel) => {
    switch (level) {
      case 'error': return 'danger';
      case 'warn': return 'warning';
      case 'info': return 'info';
      case 'network': return 'primary';
      case 'debug': return 'secondary';
      default: return 'secondary';
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString() + '.' + timestamp.getMilliseconds().toString().padStart(3, '0');
  };

  return (
    <Modal show={show} onHide={onHide} size="xl" fullscreen="lg-down">
      <Modal.Header closeButton className="bg-dark text-light">
        <Modal.Title>
          <FaBug className="me-2" />
          Development Debug Panel
        </Modal.Title>
      </Modal.Header>
      
      <Modal.Body className="p-0">
        {/* Controls */}
        <div className="border-bottom p-3 bg-light">
          <div className="row align-items-center g-3">
            <div className="col-md-4">
              <InputGroup size="sm">
                <InputGroup.Text><FaFilter /></InputGroup.Text>
                <Form.Select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value as LogLevel | 'all')}
                >
                  <option value="all">All Levels</option>
                  <option value="error">Errors</option>
                  <option value="warn">Warnings</option>
                  <option value="info">Info</option>
                  <option value="network">Network</option>
                  <option value="debug">Debug</option>
                </Form.Select>
              </InputGroup>
            </div>
            <div className="col-md-4">
              <Form.Control
                size="sm"
                type="text"
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="col-md-4">
              <div className="d-flex gap-2">
                <Button size="sm" variant="outline-secondary" onClick={copyLogs}>
                  <FaCopy className="me-1" />
                  Copy
                </Button>
                <Button size="sm" variant="outline-secondary" onClick={downloadLogs}>
                  <FaDownload className="me-1" />
                  Download
                </Button>
                <Button size="sm" variant="outline-danger" onClick={clearLogs}>
                  <FaTrash className="me-1" />
                  Clear
                </Button>
              </div>
            </div>
          </div>
          
          <div className="mt-2 d-flex gap-2 align-items-center">
            <small className="text-muted">Total: {filteredLogs.length} logs</small>
            {logs.length > 0 && (
              <>
                <Badge bg="danger">{logs.filter(l => l.level === 'error').length}</Badge>
                <Badge bg="warning">{logs.filter(l => l.level === 'warn').length}</Badge>
                <Badge bg="primary">{logs.filter(l => l.level === 'network').length}</Badge>
                <Badge bg="info">{logs.filter(l => l.level === 'info').length}</Badge>
                <Badge bg="secondary">{logs.filter(l => l.level === 'debug').length}</Badge>
              </>
            )}
          </div>
        </div>

        {/* Logs */}
        <div style={{ height: '60vh', overflow: 'auto' }} className="p-3">
          {filteredLogs.length === 0 ? (
            <div className="text-center text-muted py-5">
              <FaBug size={48} className="mb-3 opacity-50" />
              <p>No logs to display</p>
              <small>Logs will appear here as your application runs</small>
            </div>
          ) : (
            <div className="d-flex flex-column gap-2">
              {filteredLogs.map((log) => (
                <Card key={log.id} className="border-start border-3" style={{
                  borderLeftColor: log.level === 'error' ? '#dc3545' : 
                                 log.level === 'warn' ? '#ffc107' :
                                 log.level === 'network' ? '#0d6efd' :
                                 log.level === 'info' ? '#0dcaf0' : '#6c757d'
                }}>
                  <Card.Body className="p-2">
                    <div className="d-flex align-items-start justify-content-between">
                      <div className="flex-grow-1">
                        <div className="d-flex align-items-center gap-2 mb-1">
                          <Badge bg={getLevelBadgeVariant(log.level)} className="small">
                            {log.level.toUpperCase()}
                          </Badge>
                          <small className="text-muted font-monospace">
                            {formatTimestamp(log.timestamp)}
                          </small>
                          {log.source && (
                            <Badge bg="light" text="dark" className="small">
                              {log.source}
                            </Badge>
                          )}
                        </div>
                        <div className="font-monospace" style={{ fontSize: '0.85rem' }}>
                          {log.message}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline-secondary"
                        onClick={() => navigator.clipboard?.writeText(`[${log.timestamp.toISOString()}] ${log.level.toUpperCase()}: ${log.message}`)}
                      >
                        <FaCopy />
                      </Button>
                    </div>
                    
                    {(log.details || log.stack) && (
                      <Accordion className="mt-2">
                        <Accordion.Item eventKey="0">
                          <Accordion.Header>
                            <small>View Details</small>
                          </Accordion.Header>
                          <Accordion.Body>
                            {log.stack && (
                              <div className="mb-3">
                                <strong>Stack Trace:</strong>
                                <pre className="bg-light p-2 rounded mt-1" style={{ fontSize: '0.75rem', maxHeight: '200px', overflow: 'auto' }}>
                                  {log.stack}
                                </pre>
                              </div>
                            )}
                            {log.details && (
                              <div>
                                <strong>Details:</strong>
                                <pre className="bg-light p-2 rounded mt-1" style={{ fontSize: '0.75rem', maxHeight: '300px', overflow: 'auto' }}>
                                  {JSON.stringify(log.details, null, 2)}
                                </pre>
                              </div>
                            )}
                          </Accordion.Body>
                        </Accordion.Item>
                      </Accordion>
                    )}
                  </Card.Body>
                </Card>
              ))}
            </div>
          )}
        </div>
      </Modal.Body>
      
      <Modal.Footer>
        <div className="d-flex justify-content-between w-100 align-items-center">
          <small className="text-muted">
            Debug panel active - Performance may be affected
          </small>
          <Button variant="secondary" onClick={onHide}>
            Close
          </Button>
        </div>
      </Modal.Footer>
    </Modal>
  );
};

export default DebugPanel;
