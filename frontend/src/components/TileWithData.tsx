import React, { useEffect, useState } from 'react';
import { Button, ButtonGroup, Spinner } from 'react-bootstrap';
// @ts-ignore - TypeScript type declarations issue with recharts package
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DashboardTile } from './DashboardTile';
import { DashboardTileDef, previewDashboardTile } from '../api/backendRequests';
import WithTooltip from './WithTooltip';
import { formatRelativeTime, formatRefreshPeriod } from '../utils/timeUtils';
import { FaLock, FaShieldAlt } from 'react-icons/fa';

// Error type constants
const ERROR_COMPUTATION_DELETED = 'COMPUTATION_DELETED';

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
  const [error, setError] = useState<string | null>(null);
  const [isComputationDeleted, setIsComputationDeleted] = useState<boolean>(false);
  const [tsKey, setTsKey] = useState<number>(0);
  const [cache, setCache] = useState<{ rows: unknown[]; at: number } | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [lastManualRefresh, setLastManualRefresh] = useState<number>(0);

  // Get refresh interval from config, default to 30 seconds
  const refreshIntervalMs = Number((tile.config as any)?.refreshInterval ?? DEFAULT_REFRESH_INTERVAL_MS);
  const autoRefreshEnabled = (tile.config as any)?.autoRefresh !== false;

  useEffect(() => {
    let mounted = true;
    const hasExistingData = rows !== null;
    
    // Prevent concurrent requests for the same tile
    if ((loading || refreshing) && tsKey > 0) {
      return;
    }
    
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
        
        // Check if computation was deleted
        if (data && typeof data === 'object' && (data as any).error === ERROR_COMPUTATION_DELETED) {
          setIsComputationDeleted(true);
          setError((data as any).message);
          setRows([]);
          return;
        }
        
        const arr = Array.isArray(data) ? data : [];
        
        // Ensure time series data is sorted chronologically for proper chart display
        if (tile.viz_type === 'timeseries') {
          const timeField = (tile.config as any)?.timeField || 'time_start';
          arr.sort((a: any, b: any) => {
            const timeA = new Date(a[timeField]).getTime();
            const timeB = new Date(b[timeField]).getTime();
            return timeA - timeB; // Sort ascending (oldest to newest)
          });
        }
        
        setRows(arr);
        setIsComputationDeleted(false);
        setError(null);
        const now = Date.now();
        setCache({ rows: arr, at: now });
        setLastRefreshed(new Date(now));
      } catch (err) {
        if (!mounted) return;
        // Set error state for any fetch failures
        setError('Failed to load tile data');
        setIsComputationDeleted(false);
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
  }, [tile.id, tsKey]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefreshEnabled || refreshIntervalMs <= 0) return;
    
    // Minimum refresh interval of 15 seconds to prevent abuse
    const safeRefreshInterval = Math.max(refreshIntervalMs, 15000);
    
    const interval = setInterval(() => {
      setTsKey(k => k + 1);
      setCache(null);
    }, safeRefreshInterval);
    
    return () => {
      clearInterval(interval);
    };
  }, [autoRefreshEnabled, refreshIntervalMs, tile.id]);

  const handleManualRefresh = () => {
    const now = Date.now();
    // Throttle manual refresh to prevent rapid clicking (minimum 2 seconds between manual refreshes)
    if (now - lastManualRefresh < 2000) {
      return;
    }
    setLastManualRefresh(now);
    setTsKey(k => k + 1);
    setCache(null);
  };

  return (
    <div className="h-100 d-flex flex-column">
      {/* Check if tile is access restricted */}
      {tile.access_restricted ? (
        <div className="h-100 d-flex flex-column">
          <div className="d-flex justify-content-between align-items-center mb-1">
            <div className="fw-semibold d-flex align-items-center gap-2">
              <FaLock className="text-secondary" />
              <span className="text-muted">{tile.name}</span>
            </div>
          </div>
          <div className="flex-grow-1 d-flex align-items-center justify-content-center text-center p-4 border rounded bg-body-tertiary">
            <div>
              <div className="mb-3">
                <FaShieldAlt size={48} className="text-secondary opacity-50" />
              </div>
              <div className="fw-bold text-secondary mb-2">Access Restricted</div>
              <div className="text-muted small">
                {tile.restriction_message || 'You do not have permission to view this tile.'}
              </div>
              {tile.sensitivity && (
                <div className="mt-2">
                  <span className={`badge bg-${
                    tile.sensitivity === 'restricted' ? 'danger' :
                    tile.sensitivity === 'confidential' ? 'warning' :
                    tile.sensitivity === 'internal' ? 'info' : 'secondary'
                  } text-uppercase`}>
                    {tile.sensitivity} data
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <>
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
          {tile.sensitivity && tile.sensitivity !== 'public' && (
            <WithTooltip tip={`This tile contains ${tile.sensitivity} data`}>
              <span className={`badge bg-${
                tile.sensitivity === 'restricted' ? 'danger' :
                tile.sensitivity === 'confidential' ? 'warning' :
                tile.sensitivity === 'internal' ? 'info' : 'secondary'
              } text-uppercase small`}>
                <FaShieldAlt className="me-1" size={10} />
                {tile.sensitivity}
              </span>
            </WithTooltip>
          )}
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
        {isComputationDeleted ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-center p-3 border rounded bg-body-tertiary">
            <div>
              <div className="text-danger mb-2">
                <span style={{ fontSize: '2rem' }}>⚠️</span>
              </div>
              <div className="fw-bold text-danger">Computation Deleted</div>
              <div className="text-muted small mt-1">{error}</div>
              <div className="mt-2">
                <Button size="sm" variant="primary" onClick={() => onEdit && onEdit()}>
                  Select New Computation
                </Button>
              </div>
            </div>
          </div>
        ) : error ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-center p-3 border rounded bg-body-tertiary">
            <div>
              <div className="text-warning mb-2">
                <span style={{ fontSize: '2rem' }}>⚠️</span>
              </div>
              <div className="fw-bold text-warning">Error Loading Data</div>
              <div className="text-muted small mt-1">{error}</div>
              <div className="mt-2">
                <Button size="sm" variant="outline-secondary" onClick={handleManualRefresh}>
                  Retry
                </Button>
              </div>
            </div>
          </div>
        ) : loading && rows === null ? (
          <div className="text-body-secondary border rounded p-2 bg-body-tertiary">
            <Spinner animation="border" size="sm" className="me-2" />Loading…
          </div>
        ) : tile.viz_type === 'timeseries' ? (
          <div className="border rounded p-2 bg-body-tertiary flex-grow-1 d-flex flex-column" style={{ minHeight: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
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
        </>
      )}
    </div>
  );
};