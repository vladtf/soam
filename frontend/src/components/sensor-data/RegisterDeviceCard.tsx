import React from 'react';
import { Card, Button, Form } from 'react-bootstrap';

export interface RegisterDeviceCardProps {
    activePartition: string;
    ingestionId: string;
    setIngestionId: (v: string) => void;
    name: string;
    setName: (v: string) => void;
    description: string;
    setDescription: (v: string) => void;
    onRegister: (e: React.FormEvent) => void;
}

const RegisterDeviceCard: React.FC<RegisterDeviceCardProps> = ({
    activePartition,
    ingestionId,
    setIngestionId,
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
                        }}>Use as ingestion_id and name</Button>
                    </div>
                )}
                <Form onSubmit={onRegister}>
                    <Form.Group controlId="ingestionId" className="mb-2">
                        <Form.Label className="mb-1">Ingestion ID</Form.Label>
                        <Form.Control size="sm" type="text" value={ingestionId} onChange={(e) => setIngestionId(e.target.value)} placeholder="Required: ingestion_id (source)" required />
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
