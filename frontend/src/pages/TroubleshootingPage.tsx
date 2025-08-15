import React, { useEffect, useState } from 'react';
import { Card, Button, Table, Badge } from 'react-bootstrap';
import { getConfig } from '../config';
import { flushErrorQueue } from '../errors';
import { useError } from '../context/ErrorContext';

interface ClientErrorRow {
  id: number;
  message: string;
  stack?: string | null;
  url?: string | null;
  component?: string | null;
  context?: string | null;
  severity?: string | null;
  user_agent?: string | null;
  session_id?: string | null;
  extra?: Record<string, unknown> | null;
  created_at?: string | null;
}

const TroubleshootingPage: React.FC = () => {
  const { backendUrl } = getConfig();
  const { setError } = useError();
  const [rows, setRows] = useState<ClientErrorRow[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const load = async () => {
    setLoading(true);
    try {
      await flushErrorQueue();
      const res = await fetch(`${backendUrl}/errors/?limit=200`);
      const data = await res.json();
      setRows(data || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : (e as any));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="container py-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h3 className="m-0">Troubleshooting</h3>
        <div className="d-flex gap-2">
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={() => { flushErrorQueue(true).catch(() => {}); }}
          >
            Flush local queue
          </Button>
          <Button variant="primary" size="sm" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</Button>
        </div>
      </div>

      <Card className="shadow-sm">
        <Card.Header className="bg-body-tertiary">Client Exceptions</Card.Header>
        <div className="table-responsive">
          <Table hover size="sm" className="mb-0">
            <thead>
              <tr>
                <th>ID</th>
                <th>When</th>
                <th>Severity</th>
                <th>Component</th>
                <th>Context</th>
                <th>Message</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{r.created_at ? new Date(r.created_at).toLocaleString() : '-'}</td>
                  <td>
                    <Badge bg={r.severity === 'fatal' || r.severity === 'error' ? 'danger' : (r.severity === 'warn' ? 'warning' : 'secondary')}>{r.severity || 'info'}</Badge>
                  </td>
                  <td>{r.component || '-'}</td>
                  <td>{r.context || '-'}</td>
                  <td style={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.message}>{r.message}</td>
                  <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.url || ''}>{r.url || '-'}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-body-secondary py-3">No client errors recorded</td>
                </tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card>
    </div>
  );
};

export default TroubleshootingPage;


