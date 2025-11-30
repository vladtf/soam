import React, { useMemo } from 'react';
import { Card, Button, Form, Badge, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { SensorData, DataSensitivity } from '../../api/backendRequests';
import { FaInfoCircle, FaShieldAlt } from 'react-icons/fa';

export interface RegisterDeviceFormData {
    ingestionId: string;
    name: string;
    description: string;
    sensitivity: DataSensitivity;
    dataRetentionDays: number;
}

export interface RegisterDeviceCardProps {
    activePartition: string;
    ingestionId: string;
    setIngestionId: (v: string) => void;
    name: string;
    setName: (v: string) => void;
    description: string;
    setDescription: (v: string) => void;
    sensitivity?: DataSensitivity;
    setSensitivity?: (v: DataSensitivity) => void;
    dataRetentionDays?: number;
    setDataRetentionDays?: (v: number) => void;
    onRegister: (e: React.FormEvent) => void;
    sensorData: SensorData[];
    isAdmin?: boolean;
}

const SENSITIVITY_OPTIONS: { value: DataSensitivity; label: string; description: string; color: string }[] = [
    { value: 'public', label: 'Public', description: 'Open access (weather, air quality)', color: 'success' },
    { value: 'internal', label: 'Internal', description: 'Business data, internal use', color: 'info' },
    { value: 'confidential', label: 'Confidential', description: 'Restricted access (Admin only)', color: 'warning' },
    { value: 'restricted', label: 'Restricted', description: 'Highly sensitive (Admin + audit)', color: 'danger' },
];

const RegisterDeviceCard: React.FC<RegisterDeviceCardProps> = ({
    activePartition,
    ingestionId,
    setIngestionId,
    name,
    setName,
    description,
    setDescription,
    sensitivity = 'internal',
    setSensitivity,
    dataRetentionDays = 90,
    setDataRetentionDays,
    onRegister,
    sensorData,
    isAdmin = false,
}) => {
    // Extract unique ingestion IDs from sensor data
    const availableIngestionIds = useMemo(() => {
        const uniqueIds = new Set<string>();
        
        sensorData.forEach((data) => {
            // Only check ingestion_id field
            const ingestionId = data.ingestion_id;
            
            if (ingestionId && typeof ingestionId === 'string' && ingestionId.trim()) {
                uniqueIds.add(ingestionId.trim());
            }
        });
        
        return Array.from(uniqueIds).sort();
    }, [sensorData]);

    const handleIngestionIdSelect = (selectedId: string) => {
        setIngestionId(selectedId);
        // Also auto-fill the name if it's empty
        if (!name && selectedId) {
            setName(selectedId);
        }
    };

    const selectedSensitivity = SENSITIVITY_OPTIONS.find(s => s.value === sensitivity);

    return (
        <Card className="mb-3">
            <Card.Header className="py-2 d-flex align-items-center">
                <FaShieldAlt className="me-2 text-primary" />
                <strong>Register Device</strong>
            </Card.Header>
            <Card.Body>
                {activePartition && (
                    <div className="mb-2 small">
                        Using partition: <code>{activePartition}</code>
                        <Button size="sm" variant="link" className="ms-2 p-0" onClick={() => {
                            setIngestionId(activePartition);
                            setName(activePartition);
                        }}>Use as ingestion_id and name</Button>
                    </div>
                )}
                <Form onSubmit={onRegister}>
                    <Form.Group controlId="ingestionId" className="mb-2">
                        <Form.Label className="mb-1">Ingestion ID</Form.Label>
                        <Form.Select 
                            size="sm" 
                            value={ingestionId} 
                            onChange={(e) => handleIngestionIdSelect(e.target.value)}
                            required
                        >
                            <option value="">Select an ingestion ID...</option>
                            {availableIngestionIds.map((id) => (
                                <option key={id} value={id}>
                                    {id}
                                </option>
                            ))}
                        </Form.Select>
                        {availableIngestionIds.length > 0 && (
                            <Form.Text className="text-muted">
                                Found {availableIngestionIds.length} unique ID(s) in sensor data
                            </Form.Text>
                        )}
                    </Form.Group>
                    <Form.Group controlId="deviceName" className="mb-2">
                        <Form.Label className="mb-1">Name</Form.Label>
                        <Form.Control size="sm" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional display name" />
                    </Form.Group>
                    <Form.Group controlId="deviceDesc" className="mb-3">
                        <Form.Label className="mb-1">Description</Form.Label>
                        <Form.Control size="sm" as="textarea" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
                    </Form.Group>
                    
                    {/* Data Sensitivity Section */}
                    <hr className="my-3" />
                    <h6 className="mb-2">
                        <FaShieldAlt className="me-1 text-warning" />
                        Data Sensitivity Classification
                    </h6>
                    
                    <Form.Group controlId="sensitivity" className="mb-2">
                        <Form.Label className="mb-1 d-flex align-items-center">
                            Sensitivity Level
                            <OverlayTrigger
                                placement="right"
                                overlay={<Tooltip>Determines who can access data from this sensor</Tooltip>}
                            >
                                <span className="ms-1 text-muted" style={{ cursor: 'help' }}><FaInfoCircle size={12} /></span>
                            </OverlayTrigger>
                        </Form.Label>
                        <Form.Select
                            size="sm"
                            value={sensitivity}
                            onChange={(e) => setSensitivity?.(e.target.value as DataSensitivity)}
                        >
                            {SENSITIVITY_OPTIONS.map((option) => {
                                // Non-admins can only select public or internal
                                const disabled = !isAdmin && (option.value === 'confidential' || option.value === 'restricted');
                                return (
                                    <option key={option.value} value={option.value} disabled={disabled}>
                                        {option.label} - {option.description}{disabled ? ' (Admin only)' : ''}
                                    </option>
                                );
                            })}
                        </Form.Select>
                        {selectedSensitivity && (
                            <div className="mt-1">
                                <Badge bg={selectedSensitivity.color}>{selectedSensitivity.label}</Badge>
                                <small className="text-muted ms-2">{selectedSensitivity.description}</small>
                            </div>
                        )}
                    </Form.Group>

                    <Form.Group controlId="dataRetentionDays" className="mb-2">
                        <Form.Label className="mb-1 d-flex align-items-center">
                            Data Retention (days)
                            <OverlayTrigger
                                placement="right"
                                overlay={<Tooltip>How long to keep data before automatic deletion</Tooltip>}
                            >
                                <span className="ms-1 text-muted" style={{ cursor: 'help' }}><FaInfoCircle size={12} /></span>
                            </OverlayTrigger>
                        </Form.Label>
                        <Form.Control
                            size="sm"
                            type="number"
                            min={1}
                            max={3650}
                            value={dataRetentionDays}
                            onChange={(e) => setDataRetentionDays?.(parseInt(e.target.value) || 90)}
                        />
                    </Form.Group>

                    <div className="d-grid">
                        <Button type="submit" size="sm" variant="primary">
                            <FaShieldAlt className="me-1" />
                            Register Device
                        </Button>
                    </div>
                </Form>
            </Card.Body>
        </Card>
    );
};

export default RegisterDeviceCard;
