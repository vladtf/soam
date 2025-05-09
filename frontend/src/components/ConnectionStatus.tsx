import React, { useEffect, useState } from 'react';
import { Card, ListGroup, Button } from 'react-bootstrap';
import ConnectionConfigModal from './ConnectionConfigModal';

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
    const [showConfig, setShowConfig] = useState(false);

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

    const handleSwitch = async (id: number) => {
        try {
            await fetch('http://localhost:8000/switchBroker', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });
        } catch (error) {
            console.error(`Error switching to connection ${id}:`, error);
        }
    };

    return (
        <>
            <Card className="mb-3">
                <Card.Header>Connection Status</Card.Header>
                <ListGroup variant="flush">
                    {connections.length > 0 ? (
                        connections.map((info, idx) => {
                            const isActive = active && active.id === info.id;
                            return (
                                <ListGroup.Item key={info.id || idx}>
                                    <div>
                                        <strong>ID:</strong> {info.id || 'N/A'} | <strong>Status:</strong>{" "}
                                        <span style={{
                                            display: "inline-block",
                                            width: "10px",
                                            height: "10px",
                                            borderRadius: "50%",
                                            backgroundColor: isActive ? "green" : "red",
                                            marginRight: "5px"
                                        }}></span>
                                        {isActive ? "Active" : "Inactive"}
                                    </div>
                                    <div>
                                        <strong>Connection Type:</strong> {info.connectionType || 'N/A'}
                                    </div>
                                    {info.connectionType === 'mqtt' && (
                                        <div>
                                            <strong>Broker:</strong> {info.broker || 'N/A'}, <strong>Port:</strong> {info.port || 'N/A'}, <strong>Topic:</strong> {info.topic || 'N/A'}
                                        </div>
                                    )}
                                    <div className="mt-2">
                                        <Button
                                            variant={isActive ? "success" : "primary"}
                                            size="sm"
                                            onClick={() => handleSwitch(info.id!)}
                                            disabled={isActive ?? false}
                                        >
                                            {isActive ? "Active" : "Switch"}
                                        </Button>
                                    </div>
                                </ListGroup.Item>
                            );
                        })
                    ) : (
                        <ListGroup.Item>No connections configured</ListGroup.Item>
                    )}
                </ListGroup>
                <Card.Footer>
                    <Button variant="secondary" onClick={() => setShowConfig(true)}>
                        Configure Connection
                    </Button>
                </Card.Footer>
            </Card>
            <ConnectionConfigModal show={showConfig} handleClose={() => setShowConfig(false)} />
        </>
    );
};

export default ConnectionStatus;
