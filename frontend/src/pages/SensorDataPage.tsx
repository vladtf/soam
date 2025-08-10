import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Spinner, Form, Button, Badge, Card, InputGroup } from 'react-bootstrap';
// @ts-ignore - optional types
import ReactJson from 'react-json-view';
import ConnectionStatus from '../components/ConnectionStatus';
import ThemedTable from '../components/ThemedTable';
import { fetchSensorData, SensorData, listDevices, registerDevice, toggleDevice, deleteDevice, Device, fetchPartitions, setBufferMaxRows } from '../api/backendRequests';
import { useError } from '../context/ErrorContext';

const SensorDataPage: React.FC = () => {
    const { setError } = useError();
    const [data, setData] = useState<SensorData[]>([]);
    const [devices, setDevices] = useState<Device[]>([]);
    const [sensorId, setSensorId] = useState('');
    const [ingestionId, setIngestionId] = useState<string>('');
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [knownIds, setKnownIds] = useState<string[]>([]);
    const [manualId, setManualId] = useState('');
    const [useManual, setUseManual] = useState(false);
    const [partitions, setPartitions] = useState<string[]>([]);
    const [activePartition, setActivePartition] = useState<string>('');
    const [bufferSize, setBufferSize] = useState<number>(100);
    const [viewMode, setViewMode] = useState<'table' | 'json'>('json');

    useEffect(() => {
        const fetchDataNow = async () => {
            try {
                const sensorData = await fetchSensorData(activePartition || undefined);
                setData(sensorData);
                const ids = Array.from(new Set((sensorData || []).map((r: any) => (r?.sensorId ?? r?.['sensor-id'] ?? r?.sensor_id)).filter(Boolean)));
                setKnownIds(ids);
                if (!useManual && ids.length && !sensorId) setSensorId(ids[0]);
            } catch (err: unknown) {
                console.error('Error fetching sensor data:', err);
                setError(err instanceof Error ? err.message : (err as any));
            }
        };

        const loadParts = async () => {
            try {
                const parts = await fetchPartitions();
                setPartitions(parts);
            } catch {
                // ignore
            }
        };

        loadParts();
        fetchDataNow();
        const interval = setInterval(fetchDataNow, 5000);
        return () => clearInterval(interval);
    }, [setError, activePartition, useManual, sensorId]);

    useEffect(() => {
        const loadDevices = async () => {
            try {
                const rows = await listDevices();
                setDevices(rows);
            } catch (err) {
                console.error('Error listing devices:', err);
                setError(err instanceof Error ? err.message : (err as any));
            }
        };
        loadDevices();
    }, [setError]);

    useEffect(() => {
        if (useManual) return;
        const deviceIds = devices.map((d) => d.sensor_id).filter(Boolean) as string[];
        const available = Array.from(new Set([...(knownIds || []), ...deviceIds]));
        if (!sensorId && available.length > 0) setSensorId(available[0]);
    }, [devices, knownIds, useManual, sensorId]);

    const onRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const chosenId = (useManual ? manualId : sensorId).trim();
            await registerDevice({ sensor_id: chosenId, name: name.trim() || undefined, description: description.trim() || undefined, enabled: true, ingestion_id: ingestionId || undefined });
            setSensorId('');
            setIngestionId('');
            setName('');
            setDescription('');
            setManualId('');
            setUseManual(false);
            const rows = await listDevices();
            setDevices(rows);
        } catch (err) {
            console.error('Error registering device:', err);
            setError(err instanceof Error ? err.message : (err as any));
        }
    };

    const onToggle = async (id: number) => {
        try {
            const updated = await toggleDevice(id);
            setDevices((prev) => prev.map((d) => (d.id === id ? updated : d)));
        } catch (err) {
            console.error('Error toggling device:', err);
            setError(err instanceof Error ? err.message : (err as any));
        }
    };

    const onDelete = async (id: number) => {
        try {
            await deleteDevice(id);
            setDevices((prev) => prev.filter((d) => d.id !== id));
        } catch (err) {
            console.error('Error deleting device:', err);
            setError(err instanceof Error ? err.message : (err as any));
        }
    };

    const applyBufferSize = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await setBufferMaxRows(Math.max(1, bufferSize));
        } catch {
            // ignore UI
        }
    };

    // Build table columns dynamically from incoming data
    const tableColumns: string[] = React.useMemo(() => {
        const keys = new Set<string>();
        for (const row of data) {
            Object.keys(row as Record<string, unknown>).forEach((k) => keys.add(k));
        }
        // Prefer common keys first
        const preferred = ['timestamp', 'time', 'sensorId', 'sensor-id', 'sensor_id', 'temperature', 'humidity', 'ingestion_id'];
        const ordered: string[] = [];
        for (const p of preferred) if (keys.has(p)) ordered.push(p);
        for (const k of Array.from(keys)) if (!ordered.includes(k)) ordered.push(k);
        return ordered.slice(0, 12); // cap to 12 columns for readability
    }, [data]);

    const renderValue = (v: unknown) => {
        if (v === null || v === undefined) return '-';
        if (typeof v === 'object') return JSON.stringify(v);
        const s = String(v);
        return s.length > 80 ? s.slice(0, 77) + '…' : s;
    };

    return (
        <Container className="pt-3 pb-4">
            <ConnectionStatus />

            {/* Top controls bar */}
            <Card className="mb-3">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-center">
                        <Col lg={4} md={6}>
                            <Form.Group controlId="partitionSelect" className="mb-0">
                                <InputGroup size="sm">
                                    <InputGroup.Text>Partition</InputGroup.Text>
                                    <Form.Select value={activePartition} onChange={(e) => setActivePartition(e.target.value)}>
                                        <option value="">All</option>
                                        {partitions.map((p) => (
                                            <option key={p} value={p}>{p}</option>
                                        ))}
                                    </Form.Select>
                                    <InputGroup.Text className="text-muted">{partitions.length}</InputGroup.Text>
                                </InputGroup>
                            </Form.Group>
                        </Col>
                        <Col lg={4} md={6}>
                            <Form onSubmit={applyBufferSize} className="mb-0">
                                <InputGroup size="sm">
                                    <InputGroup.Text>Max rows</InputGroup.Text>
                                    <Form.Control type="number" min={1} value={bufferSize} onChange={(e) => setBufferSize(parseInt(e.target.value || '1', 10))} />
                                    <Button type="submit" variant="outline-secondary">Apply</Button>
                                </InputGroup>
                            </Form>
                        </Col>
                        <Col lg={4} md={12}>
                            <Form.Group className="mb-0">
                                <InputGroup size="sm">
                                    <InputGroup.Text>View</InputGroup.Text>
                                    <Form.Select value={viewMode} onChange={(e) => setViewMode(e.target.value as 'table' | 'json')}>
                                        <option value="json">JSON</option>
                                        <option value="table">Table</option>
                                    </Form.Select>
                                </InputGroup>
                            </Form.Group>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            <Row className="g-3">
                {/* Main data viewer */}
                <Col lg={7}>
                    <Card>
                        <Card.Header className="py-2">
                            <strong>Sensor Data</strong>
                        </Card.Header>
                        <Card.Body className="p-0">
                            {viewMode === 'table' ? (
                                <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
                                    {data && data.length > 0 ? (
                                        <ThemedTable size="sm" responsive hover className="mb-0">
                                            <thead>
                                                <tr>
                                                    {tableColumns.map((c) => (
                                                        <th key={c}>{c}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {data.map((row, idx) => (
                                                    <tr key={idx}>
                                                        {tableColumns.map((c) => (
                                                            <td key={c}>{renderValue((row as any)[c])}</td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </ThemedTable>
                                    ) : (
                                        <div className="d-flex align-items-center justify-content-center py-5">
                                            <Spinner animation="border" role="status" className="me-2" />
                                            <span className="text-muted">Waiting for data…</span>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="p-2" style={{ maxHeight: '70vh', overflow: 'auto' }}>
                                    {data && data.length > 0 ? (
                                        <ReactJson src={data} theme="tomorrow" collapsed={false} />
                                    ) : (
                                        <div className="d-flex align-items-center justify-content-center py-5">
                                            <Spinner animation="border" role="status" className="me-2" />
                                            <span className="text-muted">Waiting for data…</span>
                                        </div>
                                    )}
                                </div>
                            )}
                        </Card.Body>
                    </Card>
                </Col>

                {/* Side panel: register + devices */}
                <Col lg={5}>
                    <Card className="mb-3">
                        <Card.Header className="py-2">
                            <strong>Register Device</strong>
                        </Card.Header>
                        <Card.Body>
                            {activePartition && (
                                <div className="mb-2 small">
                                    Using partition: <code>{activePartition}</code>
                                    <Button size="sm" variant="link" className="ms-2 p-0" onClick={() => {
                                        setIngestionId(activePartition);
                                        setName(activePartition);
                                        try {
                                            const firstId = (data || []).map((r: any) => r?.sensorId ?? r?.['sensor-id']).find(Boolean);
                                            if (firstId) setSensorId(String(firstId));
                                        } catch {
                                            // ignore
                                        }
                                    }}>Use as ingestion_id and name</Button>
                                </div>
                            )}
                            <Form onSubmit={onRegister}>
                                <Form.Group controlId="ingestionId" className="mb-2">
                                    <Form.Label className="mb-1">Ingestion ID</Form.Label>
                                    <Form.Control size="sm" type="text" value={ingestionId} onChange={(e) => setIngestionId(e.target.value)} placeholder="Optional ingestion_id (source)" />
                                </Form.Group>
                                <Form.Group controlId="sensorId" className="mb-2">
                                    <Form.Label className="mb-1">Sensor ID</Form.Label>
                                    {!useManual ? (
                                        <>
                                            {(() => {
                                                const available = Array.from(new Set([...(knownIds || []), ...devices.map((d) => d.sensor_id).filter(Boolean) as string[]]));
                                                return (
                                                    <Form.Select size="sm" value={sensorId} onChange={(e) => setSensorId(e.target.value)} aria-label="Known sensor IDs">
                                                        {available.length === 0 ? (
                                                            <option value="">No known IDs yet</option>
                                                        ) : (
                                                            available.map((id) => (
                                                                <option key={id} value={id}>
                                                                    {id}
                                                                </option>
                                                            ))
                                                        )}
                                                    </Form.Select>
                                                );
                                            })()}
                                            <Form.Text className="text-muted">Choose from seen devices or switch to manual.</Form.Text>
                                        </>
                                    ) : (
                                        <Form.Control size="sm" type="text" value={manualId} onChange={(e) => setManualId(e.target.value)} required placeholder="e.g., Sensor123" />
                                    )}
                                    <div className="mt-2">
                                        <Form.Check type="switch" id="useManualSwitch" label="Enter manually" checked={useManual} onChange={(e) => setUseManual(e.target.checked)} />
                                    </div>
                                </Form.Group>
                                <Form.Group controlId="deviceName" className="mb-2">
                                    <Form.Label className="mb-1">Name</Form.Label>
                                    <Form.Control size="sm" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional display name" />
                                </Form.Group>
                                <Form.Group controlId="deviceDesc" className="mb-3">
                                    <Form.Label className="mb-1">Description</Form.Label>
                                    <Form.Control size="sm" as="textarea" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
                                </Form.Group>
                                <div className="d-grid">
                                    <Button type="submit" size="sm" variant="primary">Register</Button>
                                </div>
                            </Form>
                        </Card.Body>
                    </Card>

                    <Card>
                        <Card.Header className="py-2">
                            <strong>Registered Devices</strong>
                        </Card.Header>
                        <Card.Body className="p-0">
                            <div style={{ maxHeight: '40vh', overflow: 'auto' }}>
                                <ThemedTable size="sm" responsive hover className="mb-0">
                                    <thead>
                                        <tr>
                                            <th>ID</th>
                                            <th>Sensor ID</th>
                                            <th>Name</th>
                                            <th>Status</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {devices.length === 0 ? (
                                            <tr><td colSpan={5} className="text-center text-muted">No devices</td></tr>
                                        ) : devices.map(d => (
                                            <tr key={d.id}>
                                                <td>{d.id}</td>
                                                <td>{d.sensor_id}</td>
                                                <td>{d.name || '-'}</td>
                                                <td>
                                                    <Badge bg={d.enabled ? 'success' : 'secondary'}>{d.enabled ? 'On' : 'Off'}</Badge>
                                                </td>
                                                <td className="text-end">
                                                    <Button size="sm" variant="outline-secondary" className="me-2" onClick={() => d.id && onToggle(d.id)}>Toggle</Button>
                                                    <Button size="sm" variant="outline-danger" onClick={() => d.id && onDelete(d.id)}>Delete</Button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </ThemedTable>
                            </div>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>
        </Container>
    );
};

export default SensorDataPage;