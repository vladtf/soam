import React, { useEffect, useState } from 'react';
import { Card, ListGroup } from 'react-bootstrap';

interface ConnectionInfo {
    id?: number;
    connectionType?: string;
    broker?: string;
    port?: number;
    topic?: string;
}

const ConnectionStatus: React.FC = () => {
    const [connections, setConnections] = useState<ConnectionInfo[]>([]);
    const [active, setActive] = useState<ConnectionInfo | null>(null);

    useEffect(() => {
        const fetchConnections = async () => {
            try {
                const response = await fetch('http://localhost:8000/connections');
                const data = await response.json();
                setConnections(data.connections || []);
                setActive(data.active || null);
            } catch (error) {
                console.error('Error fetching connection statuses:', error);
            }
        };

        fetchConnections();
        const interval = setInterval(fetchConnections, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <Card className="mb-3">
            <Card.Header>Connection Status</Card.Header>
            <ListGroup variant="flush">
                {connections.length > 0 ? (
                    connections.map((info, idx) => (
                        <ListGroup.Item key={info.id || idx}>
                            <strong>ID:</strong> {info.id || 'N/A'} | <strong>Status:</strong> {active && active.id === info.id ? "Active" : "Inactive"}<br />
                            <strong>Connection Type:</strong> {info.connectionType || 'N/A'}<br />
                            {info.connectionType === 'mqtt' && (
                                <>
                                    <strong>Broker:</strong> {info.broker || 'N/A'}, <strong>Port:</strong> {info.port || 'N/A'}, <strong>Topic:</strong> {info.topic || 'N/A'}
                                </>
                            )}
                        </ListGroup.Item>
                    ))
                ) : (
                    <ListGroup.Item>No connections configured</ListGroup.Item>
                )}
            </ListGroup>
        </Card>
    );
};

export default ConnectionStatus;
