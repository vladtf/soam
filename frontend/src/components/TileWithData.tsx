import React, { useEffect, useState } from 'react';
import { Button, ButtonGroup, Spinner } from 'react-bootstrap';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DashboardTile } from './DashboardTile';
import { DashboardTileDef, previewDashboardTile } from '../api/backendRequests';
import WithTooltip from './WithTooltip';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';

// Default refresh interval in milliseconds
const DEFAULT_REFRESH_INTERVAL_MS = 30000;

interface TileWithDataProps {
  tile: DashboardTileDef;
  dragEnabled: boolean;
  onDelete?: () => void;
  onEdit?: () => void;
}

export const TileWithData: React.FC<TileWithDataProps> = ({ 
  tile, 
  dragEnabled, 
  onDelete, 
  onEdit 
}) => {
  const [rows, setRows] = useState<unknown[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [tsKey, setTsKey] = useState<number>(0);
  const [cache, setCache] = useState<{ rows: unknown[]; at: number } | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Get refresh interval from config, default to 30 seconds
  const refreshIntervalMs = Number((tile.config as any)?.refreshInterval ?? DEFAULT_REFRESH_INTERVAL_MS);
  const autoRefreshEnabled = (tile.config as any)?.autoRefresh !== false;

  useEffect(() => {
    let mounted = true;
    const hasExistingData = rows !== null;
    
    if (hasExistingData) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    
    (async () => {
      try {
        const cacheSec = Number((tile.config as any)?.cacheSec ?? 0);
        if (cache && (Date.now() - cache.at) / 1000 < cacheSec) { 
          setRows(cache.rows); 
          setLastRefreshed(new Date(cache.at));
          return; 
        }
        const data = await previewDashboardTile(tile.id!);
        if (!mounted) return;
        const arr = Array.isArray(data) ? data : [];
        setRows(arr);
        const now = Date.now();
        setCache({ rows: arr, at: now });
        setLastRefreshed(new Date(now));
      } catch {
        if (!mounted) return;
        // Don't clear existing data on error if we have it
        if (!hasExistingData) {
          setRows([]);
        }
      } finally {
        if (mounted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();
    return () => { mounted = false; };
  }, [tile.id, tsKey, rows]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefreshEnabled || refreshIntervalMs <= 0) return;
    
    const interval = setInterval(() => {
      setTsKey(k => k + 1);
      setCache(null);
    }, refreshIntervalMs);
    
    return () => {
      clearInterval(interval);
    };
  }, [autoRefreshEnabled, refreshIntervalMs, tile.id]);

  const handleManualRefresh = () => {
    setTsKey(k => k + 1);
    setCache(null);
  };

  return (
    <div className="h-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center mb-1">
        <div className="fw-semibold d-flex align-items-center gap-2" title={dragEnabled ? 'Drag to move tile' : ''}>
          <span
            className="tile-drag-handle user-select-none"
            aria-label="Drag handle"
            style={{ cursor: dragEnabled ? 'grab' as const : 'default' as const }}
          >
            ⠿
          </span>
          <span>{tile.name}</span>
        </div>
        <ButtonGroup size="sm" className="tile-controls" onMouseDown={(e) => e.stopPropagation()}>
          <WithTooltip tip="Reload the data for this tile">
            <Button variant="outline-secondary" onClick={(e) => { e.stopPropagation(); handleManualRefresh(); }}>
              Refresh
            </Button>
          </WithTooltip>
          <WithTooltip tip="Edit tile settings (computation, visualization, config)">
            <Button variant="outline-secondary" onClick={(e) => { e.stopPropagation(); onEdit && onEdit(); }}>
              Edit
            </Button>
          </WithTooltip>
          <WithTooltip tip="Remove this tile from the dashboard">
            <Button variant="outline-danger" onClick={(e) => { e.stopPropagation(); onDelete && onDelete(); }}>
              Delete
            </Button>
          </WithTooltip>
        </ButtonGroup>
      </div>
      
      {/* Refresh status info */}
      <div className="small text-body-secondary mb-2 d-flex justify-content-between align-items-center">
        <span>
          {refreshing ? (
            <span className="text-primary">
              <Spinner animation="border" size="sm" className="me-1" />
              Refreshing...
            </span>
          ) : lastRefreshed ? (
            `Updated ${formatRelativeTime(lastRefreshed)}`
          ) : (
            'Not refreshed yet'
          )}
        </span>
        <span>
          {autoRefreshEnabled ? formatRefreshPeriod(refreshIntervalMs) : 'Manual refresh only'}
        </span>
      </div>

      <div className="flex-grow-1 d-flex flex-column" style={{ minHeight: 0 }}>
        {loading && rows === null ? (
          <div className="text-body-secondary border rounded p-2 bg-body-tertiary">
            <Spinner animation="border" size="sm" className="me-2" />Loading…
          </div>
        ) : tile.viz_type === 'timeseries' ? (
          <div className="border rounded p-2 bg-body-tertiary">
            <ResponsiveContainer width="100%" height={Math.max(120, Number((tile.config as any)?.chartHeight ?? 200))}>
              <LineChart data={(rows as any[]) || []}>
                <XAxis dataKey={(tile.config as any)?.timeField || 'time_start'} hide={false} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey={(tile.config as any)?.valueField || 'avg_temperature'} stroke="#3388ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex-grow-1" style={{ minHeight: 0 }}>
            <DashboardTile title={''} viz={tile.viz_type as 'table' | 'stat' | 'timeseries'} data={rows || []} config={tile.config} />
          </div>
        )}
      </div>
    </div>
  );
};