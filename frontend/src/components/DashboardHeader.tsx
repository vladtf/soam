import React from 'react';
import { Button, ButtonGroup } from 'react-bootstrap';
import WithTooltip from './WithTooltip';

interface DashboardHeaderProps {
  dragEnabled: boolean;
  onToggleDrag: () => void;
  onOpenModal: () => void;
  onRefreshAll: () => void;
  tileCount: number;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  dragEnabled,
  onToggleDrag,
  onOpenModal,
  onRefreshAll,
  tileCount
}) => {
  return (
    <div className="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h2 className="mb-1">Smart City Dashboard</h2>
        <p className="text-body-secondary mb-0">
          Real-time insights from IoT sensors across the city • {tileCount} active tiles
        </p>
      </div>
      <ButtonGroup>
        <WithTooltip tip={dragEnabled ? "Lock tile positions" : "Enable tile repositioning"}>
          <Button 
            variant={dragEnabled ? "warning" : "outline-secondary"} 
            onClick={onToggleDrag}
          >
            {dragEnabled ? "🔓 Unlock" : "🔒 Lock"} Layout
          </Button>
        </WithTooltip>
        <WithTooltip tip="Refresh data for all tiles">
          <Button variant="outline-primary" onClick={onRefreshAll}>
            🔄 Refresh All
          </Button>
        </WithTooltip>
        <WithTooltip tip="Add a new dashboard tile with computation and visualization">
          <Button variant="primary" onClick={onOpenModal}>
            ➕ New Dashboard Tile
          </Button>
        </WithTooltip>
      </ButtonGroup>
    </div>
  );
};