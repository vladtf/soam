import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { Button, Modal, Form, Badge, Spinner, ButtonGroup } from 'react-bootstrap';
import {
  fetchOntologyGraph,
  createCity,
  createSensorNode,
  linkBuildingToCity,
  linkSensorToBuilding,
  linkSensorToCity,
  deleteOntologyNode,
  GraphData,
  GraphNode as ApiGraphNode,
} from '../api/backendRequests';

/* ================================================================
   Types
   ================================================================ */

interface D3Node extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string; // SmartCity | Building | Sensor | Address
  props: Record<string, unknown>;
}

interface D3Link extends d3.SimulationLinkDatum<D3Node> {
  sourceId: string;
  targetId: string;
  type: string;
}

/* colour palette per node label */
const NODE_COLORS: Record<string, string> = {
  SmartCity: '#6366f1',  // indigo
  Building: '#10b981',   // emerald
  Sensor: '#f59e0b',     // amber
  Address: '#8b5cf6',    // violet
};
const DEFAULT_COLOR = '#6b7280';

const NODE_RADIUS: Record<string, number> = {
  SmartCity: 22,
  Building: 16,
  Sensor: 14,
  Address: 10,
};

/* ================================================================
   Helper – derive display label from Neo4j node
   ================================================================ */
function nodeLabel(n: ApiGraphNode): string {
  const p = n.props as Record<string, string>;
  return p.name || p.sensorId || p.street || n.labels?.[0] || '?';
}

function primaryLabel(n: ApiGraphNode): string {
  return n.labels?.[0] || 'Unknown';
}

/* ================================================================
   Component
   ================================================================ */
const KnowledgeGraphViewer: React.FC = () => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showAddCity, setShowAddCity] = useState(false);
  const [showAddSensor, setShowAddSensor] = useState(false);
  const [showLink, setShowLink] = useState(false);
  const [cityName, setCityName] = useState('');
  const [cityDesc, setCityDesc] = useState('');
  const [sensorId, setSensorId] = useState('');

  // Link modal state
  const [linkType, setLinkType] = useState<'building-city' | 'sensor-building' | 'sensor-city'>('building-city');
  const [linkSource, setLinkSource] = useState('');
  const [linkTarget, setLinkTarget] = useState('');

  // Selected node for details / deletion
  const [selectedNode, setSelectedNode] = useState<D3Node | null>(null);

  /* ── Fetch graph data ──────────────────────────────────────── */
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOntologyGraph();
      setGraphData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  /* ── D3 rendering ──────────────────────────────────────────── */
  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    const width = 900, height = 600;
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .style('color', 'var(--bs-body-color)');
    svg.selectAll('*').remove();

    const container = svg.append('g');
    const zoomBehavior = d3.zoom<SVGSVGElement, unknown>().on('zoom', (e) => {
      container.attr('transform', e.transform);
    });
    svg.call(zoomBehavior);
    zoomRef.current = zoomBehavior;

    // Build D3 data
    const nodes: D3Node[] = graphData.nodes.map((n) => ({
      id: n.id,
      label: nodeLabel(n),
      type: primaryLabel(n),
      props: n.props,
    }));

    const nodeIndex = new Set(nodes.map((n) => n.id));
    const links: D3Link[] = graphData.links
      .filter((l) => nodeIndex.has(l.source) && nodeIndex.has(l.target))
      .map((l) => ({ source: l.source, target: l.target, sourceId: l.source, targetId: l.target, type: l.type }));

    // Simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<D3Node, D3Link>(links).id((d) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(30));

    // Arrow markers
    const markerTypes = [...new Set(links.map((l) => l.type))];
    svg.append('defs').selectAll('marker')
      .data(markerTypes)
      .join('marker')
      .attr('id', (d) => `arrow-${d}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25).attr('refY', 0)
      .attr('markerWidth', 8).attr('markerHeight', 8)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--bs-secondary)');

    // Links
    const linkG = container.append('g').attr('class', 'links')
      .selectAll('line').data(links).join('line')
      .attr('stroke', 'var(--bs-border-color)')
      .attr('stroke-width', 1.5)
      .attr('marker-end', (d) => `url(#arrow-${d.type})`);

    // Edge labels
    const edgeLabelG = container.append('g').attr('class', 'edge-labels')
      .selectAll('text').data(links).join('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('fill', 'var(--bs-secondary)')
      .text((d) => d.type);

    // Nodes
    const nodeG = container.append('g').attr('class', 'nodes')
      .selectAll<SVGCircleElement, D3Node>('circle').data(nodes).join('circle')
      .attr('r', (d) => NODE_RADIUS[d.type] ?? 12)
      .attr('fill', (d) => NODE_COLORS[d.type] ?? DEFAULT_COLOR)
      .attr('stroke', 'var(--bs-body-bg)')
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .on('click', (_e, d) => setSelectedNode(d))
      .call(d3.drag<SVGCircleElement, D3Node>()
        .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    // Node labels
    const labelG = container.append('g').attr('class', 'labels')
      .selectAll('text').data(nodes).join('text')
      .attr('dy', (d) => -(NODE_RADIUS[d.type] ?? 12) - 6)
      .attr('text-anchor', 'middle')
      .attr('font-size', 11)
      .attr('fill', 'currentColor')
      .text((d) => d.label);

    simulation.on('tick', () => {
      linkG
        .attr('x1', (d) => ((d.source as D3Node).x ?? 0)).attr('y1', (d) => ((d.source as D3Node).y ?? 0))
        .attr('x2', (d) => ((d.target as D3Node).x ?? 0)).attr('y2', (d) => ((d.target as D3Node).y ?? 0));
      edgeLabelG
        .attr('x', (d) => (((d.source as D3Node).x ?? 0) + ((d.target as D3Node).x ?? 0)) / 2)
        .attr('y', (d) => (((d.source as D3Node).y ?? 0) + ((d.target as D3Node).y ?? 0)) / 2 - 4);
      nodeG.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0);
      labelG.attr('x', (d) => d.x ?? 0).attr('y', (d) => d.y ?? 0);
    });
  }, [graphData]);

  /* ── Zoom helpers ──────────────────────────────────────────── */
  const zoomIn = () => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 1.3);
  const zoomOut = () => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 0.7);
  const resetZoom = () => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().call(zoomRef.current.transform, d3.zoomIdentity);

  /* ── Action handlers ───────────────────────────────────────── */
  const handleCreateCity = async () => {
    if (!cityName.trim()) return;
    try { await createCity(cityName.trim(), cityDesc.trim()); } catch { /* toast handled by doFetch */ }
    setCityName(''); setCityDesc('');
    setShowAddCity(false);
    refresh();
  };

  const handleCreateSensor = async () => {
    if (!sensorId.trim()) return;
    try { await createSensorNode(sensorId.trim()); } catch { /* */ }
    setSensorId('');
    setShowAddSensor(false);
    refresh();
  };

  const handleLink = async () => {
    if (!linkSource || !linkTarget) return;
    try {
      if (linkType === 'building-city') await linkBuildingToCity(linkSource, linkTarget);
      else if (linkType === 'sensor-building') await linkSensorToBuilding(linkSource, linkTarget);
      else await linkSensorToCity(linkSource, linkTarget);
    } catch { /* */ }
    setLinkSource(''); setLinkTarget('');
    setShowLink(false);
    refresh();
  };

  const handleDeleteNode = async () => {
    if (!selectedNode) return;
    if (!window.confirm(`Delete "${selectedNode.label}" and all its relationships?`)) return;
    try { await deleteOntologyNode(selectedNode.id); } catch { /* */ }
    setSelectedNode(null);
    refresh();
  };

  /* ── Helpers for link modal options ────────────────────────── */
  const graphNodes = graphData?.nodes ?? [];
  const cities = graphNodes.filter((n) => n.labels.includes('SmartCity'));
  const buildings = graphNodes.filter((n) => n.labels.includes('Building'));
  const sensors = graphNodes.filter((n) => n.labels.includes('Sensor'));

  const sourceOptions = linkType === 'building-city' ? buildings
    : sensors;
  const targetOptions = linkType === 'sensor-building' ? buildings
    : cities;

  const sourceLabel = (n: typeof graphNodes[number]) => (n.props as Record<string, string>).name || (n.props as Record<string, string>).sensorId || n.id;

  /* ── Legend ────────────────────────────────────────────────── */
  const legendItems = Object.entries(NODE_COLORS);

  /* ── Render ────────────────────────────────────────────────── */
  return (
    <div>
      {/* Toolbar */}
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <ButtonGroup size="sm">
          <Button variant="outline-secondary" onClick={zoomIn}>+ Zoom</Button>
          <Button variant="outline-secondary" onClick={zoomOut}>− Zoom</Button>
          <Button variant="outline-secondary" onClick={resetZoom}>Reset</Button>
        </ButtonGroup>
        <Button size="sm" variant="outline-primary" onClick={() => setShowAddCity(true)}>🏙️ Add City</Button>
        <Button size="sm" variant="outline-success" onClick={() => setShowAddSensor(true)}>📡 Add Sensor</Button>
        <Button size="sm" variant="outline-info" onClick={() => setShowLink(true)}>🔗 Link Nodes</Button>
        <Button size="sm" variant="outline-secondary" onClick={refresh} disabled={loading}>
          {loading ? <Spinner animation="border" size="sm" /> : '🔄 Refresh'}
        </Button>

        {/* Legend */}
        <div className="ms-auto d-flex gap-2 align-items-center">
          {legendItems.map(([label, color]) => (
            <Badge key={label} pill style={{ backgroundColor: color, color: '#fff', fontSize: '0.75rem' }}>
              {label}
            </Badge>
          ))}
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Graph canvas */}
      <svg ref={svgRef} style={{ width: '100%', border: '1px solid var(--bs-border-color)', borderRadius: 8, background: 'var(--bs-body-bg)' }} />

      {/* Selected node panel */}
      {selectedNode && (
        <div className="border rounded p-3 mt-2" style={{ maxWidth: 500, overflowWrap: 'break-word', wordBreak: 'break-all' }}>
          <div className="d-flex justify-content-between align-items-start gap-2">
            <div style={{ minWidth: 0, flex: 1 }}>
              <Badge bg="secondary" className="me-1">{selectedNode.type}</Badge>
              <strong style={{ wordBreak: 'break-all' }}>{selectedNode.label}</strong>
            </div>
            <div className="d-flex flex-shrink-0">
              <Button size="sm" variant="outline-danger" onClick={handleDeleteNode}>🗑 Delete</Button>
              <Button size="sm" variant="outline-secondary" className="ms-1" onClick={() => setSelectedNode(null)}>✕</Button>
            </div>
          </div>
          <hr className="my-2" />
          <small className="text-muted">Properties:</small>
          <ul className="mb-0 small">
            {Object.entries(selectedNode.props).map(([k, v]) => (
              <li key={k}><strong>{k}:</strong> {String(v)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Add City Modal ──────────────────────────────────── */}
      <Modal show={showAddCity} onHide={() => setShowAddCity(false)} centered>
        <Modal.Header closeButton><Modal.Title>🏙️ Add City</Modal.Title></Modal.Header>
        <Modal.Body>
          <Form.Group className="mb-3">
            <Form.Label>City Name</Form.Label>
            <Form.Control value={cityName} onChange={(e) => setCityName(e.target.value)} placeholder="e.g. Bucharest" />
          </Form.Group>
          <Form.Group>
            <Form.Label>Description (optional)</Form.Label>
            <Form.Control as="textarea" rows={2} value={cityDesc} onChange={(e) => setCityDesc(e.target.value)} />
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddCity(false)}>Cancel</Button>
          <Button variant="primary" onClick={handleCreateCity} disabled={!cityName.trim()}>Create</Button>
        </Modal.Footer>
      </Modal>

      {/* ── Add Sensor Modal ────────────────────────────────── */}
      <Modal show={showAddSensor} onHide={() => setShowAddSensor(false)} centered>
        <Modal.Header closeButton><Modal.Title>📡 Add Sensor Node</Modal.Title></Modal.Header>
        <Modal.Body>
          <Form.Group>
            <Form.Label>Sensor ID</Form.Label>
            <Form.Control value={sensorId} onChange={(e) => setSensorId(e.target.value)} placeholder="e.g. temp_sensor_42" />
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddSensor(false)}>Cancel</Button>
          <Button variant="success" onClick={handleCreateSensor} disabled={!sensorId.trim()}>Create</Button>
        </Modal.Footer>
      </Modal>

      {/* ── Link Nodes Modal ────────────────────────────────── */}
      <Modal show={showLink} onHide={() => setShowLink(false)} centered>
        <Modal.Header closeButton><Modal.Title>🔗 Link Nodes</Modal.Title></Modal.Header>
        <Modal.Body>
          <Form.Group className="mb-3">
            <Form.Label>Relationship Type</Form.Label>
            <Form.Select value={linkType} onChange={(e) => { setLinkType(e.target.value as typeof linkType); setLinkSource(''); setLinkTarget(''); }}>
              <option value="building-city">Building → City (locatedIn)</option>
              <option value="sensor-building">Sensor → Building (locatedIn)</option>
              <option value="sensor-city">City → Sensor (hasSensor)</option>
            </Form.Select>
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>{linkType === 'building-city' ? 'Building' : 'Sensor'}</Form.Label>
            <Form.Select value={linkSource} onChange={(e) => setLinkSource(e.target.value)}>
              <option value="">-- select --</option>
              {sourceOptions.map((n) => <option key={n.id} value={sourceLabel(n)}>{sourceLabel(n)}</option>)}
            </Form.Select>
          </Form.Group>
          <Form.Group>
            <Form.Label>{linkType === 'sensor-building' ? 'Building' : 'City'}</Form.Label>
            <Form.Select value={linkTarget} onChange={(e) => setLinkTarget(e.target.value)}>
              <option value="">-- select --</option>
              {targetOptions.map((n) => <option key={n.id} value={sourceLabel(n)}>{sourceLabel(n)}</option>)}
            </Form.Select>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowLink(false)}>Cancel</Button>
          <Button variant="info" onClick={handleLink} disabled={!linkSource || !linkTarget}>Link</Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default KnowledgeGraphViewer;
