import React from 'react';
import GridLayout from 'react-grid-layout';
import { DashboardTileDef } from '../api/backendRequests';
import { TileWithData } from './TileWithData';

interface DashboardGridProps {
  tiles: DashboardTileDef[];
  dragEnabled: boolean;
  layout: GridLayout.Layout[];
  onLayoutChange: (newLayout: GridLayout.Layout[]) => void;
  onTileEdit: (tile: DashboardTileDef) => void;
  onTileDelete: (tileId: number) => void;
}

export const DashboardGrid: React.FC<DashboardGridProps> = ({
  tiles,
  dragEnabled,
  layout,
  onLayoutChange,
  onTileEdit,
  onTileDelete
}) => {
  const handleLayoutChange = (newLayout: GridLayout.Layout[]) => {
    onLayoutChange(newLayout);
  };

  return (
    <GridLayout
      className="layout"
      layout={layout}
      cols={12}
      rowHeight={120}
      width={1200}
      onLayoutChange={handleLayoutChange}
      isDraggable={dragEnabled}
      isResizable={dragEnabled}
      autoSize={true}
      margin={[10, 10]}
      containerPadding={[0, 0]}
      useCSSTransforms={true}
      draggableHandle=".tile-drag-handle"
    >
      {tiles.map((tile) => (
        <div key={tile.id}>
          <TileWithData
            tile={tile}
            dragEnabled={dragEnabled}
            onEdit={() => onTileEdit(tile)}
            onDelete={() => onTileDelete(tile.id!)}
          />
        </div>
      ))}
    </GridLayout>
  );
};