import React, { useEffect, useState, useCallback } from 'react';
import { Card, Spinner, Badge, ListGroup, Button } from 'react-bootstrap';
import ThemedTable from './ThemedTable';
import { EnrichmentSummary, fetchEnrichmentSummary } from '../api/backendRequests';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';
import WithTooltip from './WithTooltip';

interface Props {
  minutes?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

function getAnyPartitionText(value: unknown): string {
  if (typeof value === 'number') {
    return value > 0 ? 'Yes' : 'No';
  }
  return value ? 'Yes' : 'No';
}

const DEFAULT_REFRESH_INTERVAL = 30000; // 30 seconds

const EnrichmentStatusCard: React.FC<Props> = ({ 
  minutes = 10, 
  autoRefresh = true, 
  refreshInterval = DEFAULT_REFRESH_INTERVAL
}) => {
  const [summary, setSummary] = useState<EnrichmentSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchEnrichmentSummary(minutes);
      setSummary(s);
      setLastRefreshed(new Date());
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [minutes]);

  // Initial fetch and dependency updates
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await fetchData();
    })();
    return () => { mounted = false; };
  }, [fetchData, refreshKey]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) return;
    
    const interval = setInterval(() => {
      setRefreshKey(k => k + 1);
    }, refreshInterval);
    
    return () => {
      clearInterval(interval);
    };
  }, [autoRefresh, refreshInterval]);

  const handleManualRefresh = () => {
    setRefreshKey(k => k + 1);
  };

  return (
    <Card className="shadow-sm border-body">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <span>Enrichment Status</span>
        <div className="d-flex align-items-center gap-2">
          {lastRefreshed && (
            <div className="small text-body-secondary">
              {formatRelativeTime(lastRefreshed)} • {autoRefresh ? formatRefreshPeriod(refreshInterval) : 'Manual refresh'}
            </div>
          )}
          <WithTooltip tip="Refresh enrichment status data">
            <Button 
              size="sm" 
              variant="outline-secondary" 
              onClick={handleManualRefresh}
              disabled={loading}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </Button>
          </WithTooltip>
        </div>
      </Card.Header>
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
                
                {/* Processing Metrics */}
                {summary.enriched?.processing_metrics && (
                  <div className="mt-3">
                    <div className="fw-semibold mb-1">Processing Details</div>
                    <ListGroup variant="flush" className="small">
                      <ListGroup.Item className="px-0">
                        Records Processed: 
                        <Badge bg="primary" className="ms-2">
                          {summary.enriched.processing_metrics.records_processed}
                        </Badge>
                      </ListGroup.Item>
                      <ListGroup.Item className="px-0">
                        Records Failed: 
                        <Badge 
                          bg={summary.enriched.processing_metrics.records_failed > 0 ? "warning" : "success"} 
                          className="ms-2"
                        >
                          {summary.enriched.processing_metrics.records_failed}
                        </Badge>
                      </ListGroup.Item>
                      {typeof summary.enriched.processing_metrics.error_rate_percent === 'number' && (
                        <ListGroup.Item className="px-0">
                          Error Rate: 
                          <Badge 
                            bg={summary.enriched.processing_metrics.error_rate_percent > 5 ? "danger" : "success"} 
                            className="ms-2"
                          >
                            {summary.enriched.processing_metrics.error_rate_percent}%
                          </Badge>
                        </ListGroup.Item>
                      )}
                      {typeof summary.enriched.processing_metrics.processing_duration_seconds === 'number' && (
                        <ListGroup.Item className="px-0">
                          Duration: {summary.enriched.processing_metrics.processing_duration_seconds}s
                        </ListGroup.Item>
                      )}
                      {typeof summary.enriched.processing_metrics.records_per_second === 'number' && (
                        <ListGroup.Item className="px-0">
                          Rate: {summary.enriched.processing_metrics.records_per_second} rec/s
                        </ListGroup.Item>
                      )}
                      {summary.enriched.processing_metrics.last_processing_time && (
                        <ListGroup.Item className="px-0">
                          Last Processed: {formatRelativeTime(new Date(summary.enriched.processing_metrics.last_processing_time))}
                        </ListGroup.Item>
                      )}
                    </ListGroup>
                  </div>
                )}
                
                {/* Streaming Metrics */}
                {summary.enriched?.streaming_metrics && (
                  <div className="mt-3">
                    <div className="fw-semibold mb-1">Streaming Status</div>
                    <ListGroup variant="flush" className="small">
                      <ListGroup.Item className="px-0">
                        Query Status: 
                        <Badge 
                          bg={summary.enriched.streaming_metrics.query_active ? "success" : "danger"} 
                          className="ms-2"
                        >
                          {summary.enriched.streaming_metrics.query_active ? "Active" : "Inactive"}
                        </Badge>
                      </ListGroup.Item>
                      {summary.enriched.streaming_metrics.query_name && (
                        <ListGroup.Item className="px-0">
                          Query: {summary.enriched.streaming_metrics.query_name}
                        </ListGroup.Item>
                      )}
                      {typeof summary.enriched.streaming_metrics.input_rows_per_second === 'number' && (
                        <ListGroup.Item className="px-0">
                          Input Rate: {summary.enriched.streaming_metrics.input_rows_per_second} rows/sec
                        </ListGroup.Item>
                      )}
                      {typeof summary.enriched.streaming_metrics.processing_time_ms === 'number' && (
                        <ListGroup.Item className="px-0">
                          Processing Time: {summary.enriched.streaming_metrics.processing_time_ms}ms
                        </ListGroup.Item>
                      )}
                      {summary.enriched.streaming_metrics.last_batch_timestamp && (
                        <ListGroup.Item className="px-0">
                          Last Batch: {formatRelativeTime(new Date(summary.enriched.streaming_metrics.last_batch_timestamp))}
                        </ListGroup.Item>
                      )}
                    </ListGroup>
                  </div>
                )}
                
                {/* Normalization Statistics */}
                {summary.enriched?.normalization_stats && (
                  <div className="mt-3">
                    <div className="fw-semibold mb-1">Normalization Stats</div>
                    <ListGroup variant="flush" className="small">
                      <ListGroup.Item className="px-0">
                        Active Rules: 
                        <Badge bg="info" className="ms-2">
                          {summary.enriched.normalization_stats.active_rules_count}
                        </Badge>
                      </ListGroup.Item>
                      <ListGroup.Item className="px-0">
                        Total Applications: {summary.enriched.normalization_stats.total_rules_applied}
                      </ListGroup.Item>
                      <ListGroup.Item className="px-0">
                        Field Mappings: {summary.enriched.normalization_stats.field_mappings_applied}
                      </ListGroup.Item>
                      {typeof summary.enriched.normalization_stats.normalization_success_rate === 'number' && (
                        <ListGroup.Item className="px-0">
                          Success Rate: 
                          <Badge 
                            bg={summary.enriched.normalization_stats.normalization_success_rate > 80 ? "success" : "warning"} 
                            className="ms-2"
                          >
                            {summary.enriched.normalization_stats.normalization_success_rate}%
                          </Badge>
                        </ListGroup.Item>
                      )}
                    </ListGroup>
                  </div>
                )}
              </div>
              <div>
                <div className="fw-semibold mb-1">Gold (avg) (last {minutes}m)</div>
                <ListGroup variant="flush" className="small">
                  <ListGroup.Item className="px-0">Exists: {summary.gold?.exists ? 'yes' : 'no'}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Rows: {summary.gold?.recent_rows || 0}</ListGroup.Item>
                  <ListGroup.Item className="px-0">Sensors: {summary.gold?.recent_sensors || 0}</ListGroup.Item>
                </ListGroup>
              </div>
              
              {/* Data Quality Metrics */}
              {summary.enriched?.data_quality && (
                <div>
                  <div className="fw-semibold mb-1">Data Quality</div>
                  <ListGroup variant="flush" className="small">
                    <ListGroup.Item className="px-0">
                      Ingestion IDs: 
                      <Badge bg="secondary" className="ms-2">
                        {summary.enriched.data_quality.unique_ingestion_ids}
                      </Badge>
                    </ListGroup.Item>
                    {typeof summary.enriched.data_quality.schema_compliance_rate === 'number' && (
                      <ListGroup.Item className="px-0">
                        Schema Compliance: 
                        <Badge 
                          bg={summary.enriched.data_quality.schema_compliance_rate > 80 ? "success" : 
                             summary.enriched.data_quality.schema_compliance_rate > 60 ? "warning" : "danger"} 
                          className="ms-2"
                        >
                          {summary.enriched.data_quality.schema_compliance_rate}%
                        </Badge>
                      </ListGroup.Item>
                    )}
                    <ListGroup.Item className="px-0">
                      Fields with Data: {summary.enriched.data_quality.fields_with_data.length}
                    </ListGroup.Item>
                    <ListGroup.Item className="px-0">
                      Fields Normalized: {summary.enriched.data_quality.fields_normalized.length}
                    </ListGroup.Item>
                    {Object.keys(summary.enriched.data_quality.ingestion_id_breakdown).length > 0 && (
                      <ListGroup.Item className="px-0">
                        <details 
                          className="mt-1"
                          aria-expanded={false}
                        >
                          <summary 
                            className="cursor-pointer text-primary"
                            aria-label="Show ingestion ID breakdown"
                          >
                            Ingestion ID Breakdown
                          </summary>
                          <div className="mt-2">
                            {Object.entries(summary.enriched.data_quality.ingestion_id_breakdown).map(([id, count]) => (
                              <div key={id} className="d-flex justify-content-between">
                                <code className="small">{id}</code>
                                <Badge bg="light" text="dark">{count}</Badge>
                              </div>
                            ))}
                          </div>
                        </details>
                      </ListGroup.Item>
                    )}
                  </ListGroup>
                </div>
              )}
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
