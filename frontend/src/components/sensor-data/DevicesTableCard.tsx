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
    'ID',
    'Sensor ID',
    'Name',
    'Status',
    'Created By',
    'Last Updated',
    ''
];

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
                                {TABLE_COLUMNS.map((col, idx) => (
                                    <th key={idx}>{col}</th>
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
                                    <td>{d.id}</td>
                                    <td>{d.sensor_id}</td>
                                    <td>{d.name || '-'}</td>
                                    <td>
                                        <Badge bg={d.enabled ? 'success' : 'secondary'}>{d.enabled ? 'On' : 'Off'}</Badge>
                                    </td>
                                    <td>
                                        <Badge bg="info" className="text-dark">
                                            {d.created_by || 'unknown'}
                                        </Badge>
                                        {d.updated_by && d.updated_by !== d.created_by && (
                                            <div className="small text-muted mt-1">
                                                Updated by: {d.updated_by}
                                            </div>
                                        )}
                                    </td>
                                    <td className="small text-muted">
                                        {d.updated_at ? new Date(d.updated_at).toLocaleString() : 
                                         d.created_at ? new Date(d.created_at).toLocaleString() : '-'}
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
