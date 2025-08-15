import React from 'react';
import { Card, Badge, Button } from 'react-bootstrap';
import ThemedTable from '../ThemedTable';

export interface DeviceRow {
    id?: number;
    sensor_id?: string;
    name?: string;
    enabled?: boolean;
}

export interface DevicesTableCardProps {
    devices: DeviceRow[];
    onToggle: (id: number) => void;
    onDelete: (id: number) => void;
}

const DevicesTableCard: React.FC<DevicesTableCardProps> = ({ devices, onToggle, onDelete }) => {
    return (
        <Card>
            <Card.Header className="py-2">
                <strong>Registered Devices</strong>
            </Card.Header>
            <Card.Body className="p-0">
                <div style={{ maxHeight: 'min(40vh, 400px)', overflow: 'auto' }}>
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
    );
};

export default DevicesTableCard;
