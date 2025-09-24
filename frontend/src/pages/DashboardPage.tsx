import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Form, Spinner } from 'react-bootstrap';
import { Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { toast } from 'react-toastify';
import { useDashboardData } from '../hooks/useDashboardData';
import StatisticsCards from '../components/StatisticsCards';
import TemperatureChart from '../components/TemperatureChart';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import TemperatureAlertsCard from '../components/TemperatureAlertsCard';
import PageHeader from '../components/PageHeader';
import EnrichmentStatusCard from '../components/EnrichmentStatusCard';
import { DashboardTileDef, fetchDashboardTileExamples, listDashboardTiles, createDashboardTile, listComputations, deleteDashboardTile, updateDashboardTile } from '../api/backendRequests';
import WithTooltip from '../components/WithTooltip';
import { extractDashboardTileErrorMessage } from '../utils/errorHandling';
import { TileModal } from '../components/TileModal';
import { DashboardGrid } from '../components/DashboardGrid';

// Default refresh interval in milliseconds
const DEFAULT_REFRESH_INTERVAL_MS = 30000;

const DashboardPage: React.FC = () => {
  const {
    averageTemperature,
    loading,
    refreshingTemperature,
    timeRange,
    setTimeRange,
    sparkMasterStatus,
    loadingSparkStatus,
    refreshingSparkStatus,
    sparkStreamsStatus,
    temperatureAlerts,
    loadingAlerts,
    refreshingAlerts,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refreshAll,
    refreshAlerts,
  } = useDashboardData();

  // User-defined dashboard tiles
  const [tiles, setTiles] = useState<DashboardTileDef[]>([]);
  const [tileLoading, setTileLoading] = useState(false);
  const [showTileModal, setShowTileModal] = useState(false);
  const [editing, setEditing] = useState<DashboardTileDef | null>(null);
  const [examples, setExamples] = useState<{ id: string; title: string; tile: Omit<DashboardTileDef, 'id'> }[]>([]);
  const [computations, setComputations] = useState<{ id: number; name: string }[]>([]);
  const [layouts, setLayouts] = useState<Record<string, Layout>>({});
  const [dragEnabled, setDragEnabled] = useState<boolean>(false);
  const [enableStaticCards, setEnableStaticCards] = useState<boolean>(() => {
    try {
      return localStorage.getItem('enableStaticCards') === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('enableStaticCards', enableStaticCards ? '1' : '0');
    } catch {
      // ignore
    }
  }, [enableStaticCards]);

  const loadTiles = async () => {
    setTileLoading(true);
    try {
      const [ts, ex, comps] = await Promise.all([
        listDashboardTiles().catch(() => []),
        fetchDashboardTileExamples().catch(() => ({ examples: [] })),
        listComputations().catch(() => [])
      ]);
      setTiles(ts);
      // seed layouts from tile.layout if present
      const nextLayouts: Record<string, Layout> = {};
      ts.forEach((t, idx) => {
        const lay = (t.layout as any) || {};
        nextLayouts[String(t.id)] = {
          i: String(t.id),
          x: Number(lay.x ?? 0), // Default to left edge
          y: Number(lay.y ?? idx * 4), // Stack tiles vertically
          w: Number(lay.w ?? 12), // Default to full width
          h: Number(lay.h ?? 4),
          static: false,
        } as Layout;
      });
      setLayouts(nextLayouts);
      setExamples(ex.examples || []);
      setComputations((comps || []).filter((c) => typeof c.id === 'number').map((c) => ({ id: c.id as number, name: c.name })));
    } catch (e) {
      console.warn('Failed loading tiles/examples:', e);
    } finally {
      setTileLoading(false);
    }
  };

  useEffect(() => { loadTiles(); }, []);

  const openNewTile = () => {
    const base: DashboardTileDef = { 
      name: '', 
      computation_id: 0, 
      viz_type: 'table', 
      config: { 
        refreshInterval: DEFAULT_REFRESH_INTERVAL_MS,
        autoRefresh: true 
      }, 
      enabled: true 
    };
    setEditing(base);
    setShowTileModal(true);
  };

  const openEditTile = (tile: DashboardTileDef) => {
    setEditing({ ...tile });
    setShowTileModal(true);
  };

  return (
    <Container className="pt-3 pb-4">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of key metrics and cluster status"
        onRefresh={refreshAll}
        refreshing={loading || loadingSparkStatus || loadingAlerts || refreshingTemperature || refreshingSparkStatus || refreshingAlerts}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={setAutoRefresh}
        lastUpdated={lastUpdated}
        right={
          <div className="d-flex align-items-center gap-3">
            <WithTooltip tip="Show or hide the static cards section">
              <Form.Check
                type="switch"
                id="static-cards"
                label="Static cards"
                checked={enableStaticCards}
                onChange={(e) => setEnableStaticCards(e.target.checked)}
              />
            </WithTooltip>
            <WithTooltip tip="Enable to rearrange tiles by dragging the ⠿ handle">
              <Form.Check
                type="switch"
                id="drag-mode"
                label="Drag mode"
                checked={dragEnabled}
                onChange={(e) => setDragEnabled(e.target.checked)}
              />
            </WithTooltip>
            <WithTooltip tip="Create a new dashboard tile">
              <button className="btn btn-sm btn-primary" onClick={openNewTile}>New Tile</button>
            </WithTooltip>
          </div>
        }
      />

      {/* Statistics Cards (static charts) */}
      {enableStaticCards && <StatisticsCards />}

      {/* Spark Applications */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <SparkApplicationsCard
            sparkMasterStatus={sparkMasterStatus}
            sparkStreamsStatus={sparkStreamsStatus}
            loading={loadingSparkStatus}
            refreshing={refreshingSparkStatus}
            lastUpdated={lastUpdated}
          />
        </Col>
      </Row>

      {/* Temperature Chart */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <EnrichmentStatusCard 
            minutes={10} 
            autoRefresh={autoRefresh}
            refreshInterval={30000}
          />
        </Col>
      </Row>

      {/* Temperature Alerts */}
      <Row className="g-3 mt-1">
        <Col md={8}>
          <TemperatureChart
            data={averageTemperature}
            loading={loading}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
            lastUpdated={lastUpdated}
          />
        </Col>
        <Col md={4}>
          <TemperatureAlertsCard
            alerts={temperatureAlerts}
            loading={loadingAlerts}
            lastUpdated={lastUpdated}
            onRefresh={refreshAlerts}
          />
        </Col>
      </Row>

      {/* User-defined tiles in grid */}
      {dragEnabled ? (
        <div className="small text-primary mt-2">Drag is ON. Use the <span className="user-select-none">⠿</span> handle next to each tile title to move tiles. Toggle off to finish arranging.</div>
      ) : (
        <div className="small text-body-secondary mt-2">Drag is OFF. Enable "Drag mode" to rearrange tiles.</div>
      )}
      {tileLoading ? (
        <div className="text-body-secondary"><Spinner animation="border" size="sm" className="me-2" />Loading tiles…</div>
      ) : (
        <DashboardGrid
          tiles={tiles.filter(t => t.enabled !== false)}
          dragEnabled={dragEnabled}
          layout={Object.values(layouts)}
          onLayoutChange={(newLayout: Layout[]) => {
            if (!dragEnabled) return; // ignore layout changes when drag is disabled
            // persist each tile layout
            newLayout.forEach((l: Layout) => {
              const t = tiles.find(tt => String(tt.id) === l.i);
              if (!t) return;
              const lay = { x: l.x, y: l.y, w: l.w, h: l.h };
              // optimistic update
              setLayouts(prev => ({ ...prev, [String(t.id)]: { ...l } as Layout }));
              // persist
              if (t.id) updateDashboardTile(t.id, { layout: lay }).catch(() => void 0);
            });
          }}
          onTileEdit={openEditTile}
          onTileDelete={async (tileId: number) => { 
            try {
              await deleteDashboardTile(tileId); 
              toast.success('Dashboard tile deleted successfully');
              await loadTiles(); 
            } catch (error) {
              toast.error(extractDashboardTileErrorMessage(error));
            }
          }}
        />
      )}

      {/* Tile Modal */}
      <TileModal
        show={showTileModal}
        editing={editing}
        examples={examples}
        computations={computations}
        onClose={() => {
          setShowTileModal(false);
        }}
        onSave={async (tile: DashboardTileDef) => {
          try {
            if (tile.id) {
              await updateDashboardTile(tile.id, {
                name: tile.name,
                computation_id: tile.computation_id,
                viz_type: tile.viz_type,
                config: tile.config,
                enabled: tile.enabled,
              });
              toast.success('Dashboard tile updated successfully');
            } else {
              // Create new tile with default layout
              const currentTileCount = tiles.length;
              const defaultLayout = {
                w: 12,
                h: 24,
                x: 0,
                y: currentTileCount * 6
              };
              
              const tileData = {
                ...tile,
                layout: defaultLayout
              };
              await createDashboardTile(tileData);
              toast.success('Dashboard tile created successfully');
            }
            setShowTileModal(false);
            await loadTiles();
          } catch (e) {
            toast.error(extractDashboardTileErrorMessage(e));
          }
        }}
        onEditingChange={setEditing}
      />
    </Container>
  );
};

export default DashboardPage;