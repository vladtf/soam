import React, { useEffect, useState } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import ConnectionStatus from '../components/ConnectionStatus';
import TopControlsBar from '../components/sensor-data/TopControlsBar';
import DataViewer from '../components/sensor-data/DataViewer';
import RegisterDeviceCard from '../components/sensor-data/RegisterDeviceCard';
import DevicesTableCard from '../components/sensor-data/DevicesTableCard';
import { fetchSensorData, SensorData, listDevices, registerDevice, toggleDevice, deleteDevice, Device, fetchPartitions, setBufferMaxRows } from '../api/backendRequests';
import { useError } from '../context/ErrorContext';
import { reportClientError } from '../errors';

const SensorDataPage: React.FC = () => {
    const { setError } = useError();
    const [data, setData] = useState<SensorData[]>([]);
    const [devices, setDevices] = useState<Device[]>([]);
    const [ingestionId, setIngestionId] = useState<string>('');
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [partitions, setPartitions] = useState<string[]>([]);
    const [activePartition, setActivePartition] = useState<string>('');
    const [bufferSize, setBufferSize] = useState<number>(100);
    const [viewMode, setViewMode] = useState<'table' | 'json'>('json');

    useEffect(() => {
        const fetchDataNow = async () => {
            try {
                const sensorData = await fetchSensorData(activePartition || undefined);
                setData(sensorData);
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : (err as any));
                reportClientError({ message: String(err), severity: 'error', component: 'SensorDataPage', context: 'fetchSensorData' }).catch(() => {});
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
    }, [setError, activePartition]);

    useEffect(() => {
        const loadDevices = async () => {
            try {
                const rows = await listDevices();
                setDevices(rows);
            } catch (err) {
                setError(err instanceof Error ? err.message : (err as any));
                reportClientError({ message: String(err), severity: 'error', component: 'SensorDataPage', context: 'listDevices' }).catch(() => {});
            }
        };
        loadDevices();
    }, [setError]);

    const onRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await registerDevice({ ingestion_id: ingestionId.trim(), name: name.trim() || undefined, description: description.trim() || undefined, enabled: true });
            setIngestionId('');
            setName('');
            setDescription('');
            const rows = await listDevices();
            setDevices(rows);
        } catch (err) {
            setError(err instanceof Error ? err.message : (err as any));
            reportClientError({ message: String(err), severity: 'error', component: 'SensorDataPage', context: 'registerDevice' }).catch(() => {});
        }
    };

    const onToggle = async (id: number) => {
        try {
            const updated = await toggleDevice(id);
            setDevices((prev) => prev.map((d) => (d.id === id ? updated : d)));
        } catch (err) {
            setError(err instanceof Error ? err.message : (err as any));
            reportClientError({ message: String(err), severity: 'error', component: 'SensorDataPage', context: 'toggleDevice' }).catch(() => {});
        }
    };

    const onDelete = async (id: number) => {
        try {
            await deleteDevice(id);
            setDevices((prev) => prev.filter((d) => d.id !== id));
        } catch (err) {
            setError(err instanceof Error ? err.message : (err as any));
            reportClientError({ message: String(err), severity: 'error', component: 'SensorDataPage', context: 'deleteDevice' }).catch(() => {});
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

            <TopControlsBar
                partitions={partitions}
                activePartition={activePartition}
                setActivePartition={(partition) => {
                    setActivePartition(partition);
                    // Auto-fill ingestion ID and name when selecting a partition
                    if (partition) {
                        setIngestionId(partition);
                        setName(partition);
                    }
                }}
                bufferSize={bufferSize}
                setBufferSize={setBufferSize}
                applyBufferSize={applyBufferSize}
                viewMode={viewMode}
                setViewMode={setViewMode}
            />

            <Row className="g-3">
                <Col lg={7}>
                    <DataViewer data={data} viewMode={viewMode} tableColumns={tableColumns} renderValue={renderValue} />
                </Col>
                <Col lg={5}>
                    <RegisterDeviceCard
                        activePartition={activePartition}
                        ingestionId={ingestionId}
                        setIngestionId={setIngestionId}
                        name={name}
                        setName={setName}
                        description={description}
                        setDescription={setDescription}
                        onRegister={onRegister}
                    />
                    <DevicesTableCard devices={devices} onToggle={onToggle} onDelete={onDelete} />
                </Col>
            </Row>
        </Container>
    );
};

export default SensorDataPage;