import React from 'react';
import { Card, Button, Form } from 'react-bootstrap';

export interface RegisterDeviceCardProps {
    activePartition: string;
    data: any[];
    ingestionId: string;
    setIngestionId: (v: string) => void;
    sensorId: string;
    setSensorId: (v: string) => void;
    knownIds: string[];
    devices: { sensor_id?: string }[];
    useManual: boolean;
    setUseManual: (v: boolean) => void;
    manualId: string;
    setManualId: (v: string) => void;
    name: string;
    setName: (v: string) => void;
    description: string;
    setDescription: (v: string) => void;
    onRegister: (e: React.FormEvent) => void;
}

const RegisterDeviceCard: React.FC<RegisterDeviceCardProps> = ({
    activePartition,
    data,
    ingestionId,
    setIngestionId,
    sensorId,
    setSensorId,
    knownIds,
    devices,
    useManual,
    setUseManual,
    manualId,
    setManualId,
    name,
    setName,
    description,
    setDescription,
    onRegister,
}) => {
    return (
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
    );
};

export default RegisterDeviceCard;
