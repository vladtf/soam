import React from 'react';
import { Button, ButtonGroup } from 'react-bootstrap';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void | Promise<void>;
  refreshing?: boolean;
  autoRefresh?: boolean;
  onToggleAutoRefresh?: (v: boolean) => void;
  lastUpdated?: Date | null;
  right?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  onRefresh,
  refreshing,
  autoRefresh,
  onToggleAutoRefresh,
  lastUpdated,
  right,
}) => {
  return (
    <div className="d-flex align-items-center justify-content-between mb-3">
      <div>
        <h1 className="h3 mb-1">{title}</h1>
        {subtitle && <div className="text-body-secondary small">{subtitle}</div>}
        {lastUpdated && (
          <div className="text-body-secondary small">Updated {lastUpdated.toLocaleTimeString()}</div>
        )}
      </div>
      <div className="d-flex align-items-center gap-2">
        {right}
        {(onRefresh || onToggleAutoRefresh) && (
          <ButtonGroup size="sm">
            {onRefresh && (
              <Button variant="outline-primary" onClick={onRefresh} disabled={refreshing}>
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </Button>
            )}
            {onToggleAutoRefresh && (
              <Button
                variant={autoRefresh ? 'primary' : 'outline-secondary'}
                onClick={() => onToggleAutoRefresh(!autoRefresh)}
              >
                Auto-refresh {autoRefresh ? 'ON' : 'OFF'}
              </Button>
            )}
          </ButtonGroup>
        )}
      </div>
    </div>
  );
};

export default PageHeader;
