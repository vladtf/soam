import React from 'react';
import { Card, Badge, Button } from 'react-bootstrap';
import ThemedTable from '../ThemedTable';

export interface DeviceRow {
    id?: number;
    sensor_id?: string;
    name?: string;
    enabled?: boolean;
    created_by?: string;
    updated_by?: string;
    created_at?: string;
    updated_at?: string;
}

export interface DevicesTableCardProps {
    devices: DeviceRow[];
    onToggle: (id: number) => void;
    onDelete: (id: number) => void;
}

const TABLE_COLUMNS = [
    'Device',
    'Status',
    'Created',
    'Actions'
];

const DevicesTableCard: React.FC<DevicesTableCardProps> = ({ devices, onToggle, onDelete }) => {
    return (
        <Card>
            <Card.Header className="py-2">
                <strong>Registered Devices</strong>
            </Card.Header>
            <Card.Body className="p-0">
                <div style={{ maxHeight: 'min(50vh, 500px)', overflow: 'auto' }}>
                    <ThemedTable size="sm" responsive hover className="mb-0">
                        <thead className="sticky-top bg-light">
                            <tr>
                                {TABLE_COLUMNS.map((col, idx) => (
                                    <th key={idx} className="border-bottom">{col}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {devices.length === 0 ? (
                                <tr>
                                    <td colSpan={TABLE_COLUMNS.length} className="text-center text-muted">
                                        No devices
                                    </td>
                                </tr>
                            ) : devices.map(d => (
                                <tr key={d.id}>
                                    <td>
                                        <div className="fw-bold">{d.name || 'Unnamed Device'}</div>
                                        {d.sensor_id && (
                                            <small className="text-muted">ID: {d.sensor_id}</small>
                                        )}
                                    </td>
                                    <td>
                                        <Badge bg={d.enabled ? 'success' : 'secondary'}>
                                            {d.enabled ? '🟢 Active' : '⚪ Inactive'}
                                        </Badge>
                                    </td>
                                    <td>
                                        <div className="small">
                                            <div>
                                                <Badge bg="info" className="text-dark mb-1">
                                                    {d.created_by || 'unknown'}
                                                </Badge>
                                            </div>
                                            <div className="text-muted">
                                                {d.created_at ? new Date(d.created_at).toLocaleDateString() : '-'}
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <div className="d-flex flex-column gap-1" style={{ minWidth: '80px' }}>
                                            <Button 
                                                size="sm" 
                                                variant={d.enabled ? "outline-warning" : "outline-success"} 
                                                onClick={() => d.id && onToggle(d.id)}
                                                className="py-1"
                                            >
                                                {d.enabled ? 'Disable' : 'Enable'}
                                            </Button>
                                            <Button 
                                                size="sm" 
                                                variant="outline-danger" 
                                                onClick={() => d.id && onDelete(d.id)}
                                                className="py-1"
                                            >
                                                Delete
                                            </Button>
                                        </div>
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
