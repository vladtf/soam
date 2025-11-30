import React from 'react';
import { Card, Badge, Button } from 'react-bootstrap';
import ThemedTable from '../ThemedTable';
import { FaShieldAlt } from 'react-icons/fa';
import { DataSensitivity } from '../../api/backendRequests';

export interface DeviceRow {
    id?: number;
    sensor_id?: string;
    ingestion_id?: string;
    name?: string;
    enabled?: boolean;
    sensitivity?: DataSensitivity;
    data_retention_days?: number;
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

const SENSITIVITY_COLORS: Record<DataSensitivity, string> = {
    public: 'success',
    internal: 'info',
    confidential: 'warning',
    restricted: 'danger',
};

const SENSITIVITY_LABELS: Record<DataSensitivity, string> = {
    public: 'Public',
    internal: 'Internal',
    confidential: 'Confidential',
    restricted: 'Restricted',
};

const TABLE_COLUMNS = [
    'Device',
    'Sensitivity',
    'Status',
    'Created',
    'Actions'
];

const DevicesTableCard: React.FC<DevicesTableCardProps> = ({ devices, onToggle, onDelete }) => {
    return (
        <Card>
            <Card.Header className="py-2 d-flex align-items-center">
                <FaShieldAlt className="me-2 text-primary" />
                <strong>Registered Devices</strong>
                <Badge bg="secondary" className="ms-auto">{devices.length}</Badge>
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
                            ) : devices.map(d => {
                                const sensitivity = d.sensitivity || 'internal';
                                const sensitivityColor = SENSITIVITY_COLORS[sensitivity];
                                const sensitivityLabel = SENSITIVITY_LABELS[sensitivity];
                                
                                return (
                                    <tr key={d.id}>
                                        <td>
                                            <div className="fw-bold">{d.name || 'Unnamed Device'}</div>
                                            {d.ingestion_id && (
                                                <small className="text-muted">ID: {d.ingestion_id}</small>
                                            )}
                                        </td>
                                        <td>
                                            <div className="d-flex flex-column gap-1">
                                                <Badge bg={sensitivityColor}>
                                                    <FaShieldAlt className="me-1" size={10} />
                                                    {sensitivityLabel}
                                                </Badge>
                                                <small className="text-muted">
                                                    Retention: {d.data_retention_days || 90}d
                                                </small>
                                            </div>
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
                                );
                            })}
                        </tbody>
                    </ThemedTable>
                </div>
            </Card.Body>
        </Card>
    );
};

export default DevicesTableCard;
