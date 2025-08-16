import React, { useEffect, useState } from 'react';
import { Card, Spinner, Badge, ListGroup } from 'react-bootstrap';
import ThemedTable from './ThemedTable';
import { EnrichmentSummary, fetchEnrichmentSummary } from '../api/backendRequests';

interface Props {
  minutes?: number;
}

function getAnyPartitionText(value: unknown): string {
  if (typeof value === 'number') {
    return value > 0 ? 'Yes' : 'No';
  }
  return value ? 'Yes' : 'No';
}

const EnrichmentStatusCard: React.FC<Props> = ({ minutes = 10 }) => {
  const [summary, setSummary] = useState<EnrichmentSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const s = await fetchEnrichmentSummary(minutes);
        if (!mounted) return;
        setSummary(s);
      } catch (e: unknown) {
        if (!mounted) return;
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [minutes]);

  return (
    <Card className="shadow-sm border-body">
      <Card.Header>Enrichment Status</Card.Header>
      <Card.Body>
        {loading ? (
          <div className="text-body-secondary"><Spinner animation="border" size="sm" className="me-2"/>Loading…</div>
        ) : error ? (
          <div className="text-danger small">{error}</div>
        ) : summary ? (
          <div className="small">
            <div className="mb-2">
              <span className="me-3">Registered devices: <Badge bg="secondary">{summary.registered_total || 0}</Badge></span>
              <span className="me-3">Any partition: <Badge bg="secondary">{getAnyPartitionText(summary.registered_any_partition)}</Badge></span>
              <span>Recent sensors (enriched): <Badge bg="info" text="dark">{summary.enriched?.recent_sensors || 0}</Badge></span>
            </div>
            {summary.registered_by_partition && Object.keys(summary.registered_by_partition).length > 0 && (
              <div className="mb-3">
                <div className="fw-semibold">Registered by partition</div>
                <ThemedTable size="sm" hover responsive>
                  <thead>
                    <tr><th>ingestion_id</th><th>count</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(summary.registered_by_partition || {}).map(([k, v]) => (
                      <tr key={k}><td>{k}</td><td>{v}</td></tr>
                    ))}
                  </tbody>
                </ThemedTable>
              </div>
            )}
            <div className="d-flex flex-wrap gap-3">
              <div>
                <div className="fw-semibold mb-1">Enriched (last {minutes}m)</div>
                <ListGroup variant="flush" className="small">
                  <ListGroup.Item className="px-0">Exists: {summary.enriched?.exists ? 'yes' : 'no'}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Rows: {summary.enriched?.recent_rows || 0}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Sensors: {summary.enriched?.recent_sensors || 0}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Matched sensors (registered): {summary.enriched?.matched_sensors || 0}</ListGroup.Item>
                  {summary.enriched?.sample_sensors && summary.enriched.sample_sensors.length > 0 && (
                    <ListGroup.Item className="px-0">Sample: {summary.enriched.sample_sensors.join(', ')}</ListGroup.Item>
                  )}
                </ListGroup>
              </div>
              <div>
                <div className="fw-semibold mb-1">Gold (avg) (last {minutes}m)</div>
                <ListGroup variant="flush" className="small">
                  <ListGroup.Item className="px-0">Exists: {summary.gold?.exists ? 'yes' : 'no'}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Rows: {summary.gold?.recent_rows || 0}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Sensors: {summary.gold?.recent_sensors || 0}</ListGroup.Item>
                </ListGroup>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-body-secondary">No data.</div>
        )}
      </Card.Body>
    </Card>
  );
};

export default EnrichmentStatusCard;
