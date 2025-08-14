import React, { useEffect, useState } from 'react';
import { Card, ListGroup, Button } from 'react-bootstrap';
import ConnectionConfigModal from './ConnectionConfigModal';
import { fetchConnections, switchBroker } from '../api/backendRequests';
import { useError } from '../context/ErrorContext';
import { reportClientError } from '../errors';

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

    const { setError } = useError();

    useEffect(() => {
        const loadConnections = async () => {
            try {
                const data = await fetchConnections() as { connections?: ConnectionInfo[]; active?: ConnectionInfo | null };
                setConnections(data.connections || []);
                setActive(data.active || null);
            } catch (error) {
                setError(error instanceof Error ? error.message : (error as any));
                reportClientError({ message: String(error), severity: 'warn', component: 'ConnectionStatus', context: 'fetchConnections' }).catch(() => {});
            }
        };

        loadConnections();
        const interval = setInterval(loadConnections, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleSwitch = async (id: number) => {
        try {
            await switchBroker(id);
        } catch (error) {
            setError(error instanceof Error ? error.message : (error as any));
            reportClientError({ message: String(error), severity: 'error', component: 'ConnectionStatus', context: `switchBroker:${id}` }).catch(() => {});
        }
    };

    return (
        <>
            <Card className="mb-3 shadow-sm border-body">
                <Card.Header className="bg-body-tertiary">Connection Status</Card.Header>
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
                        <ListGroup.Item className="text-body-secondary">No connections configured</ListGroup.Item>
                    )}
                </ListGroup>
                <Card.Footer className="bg-body-tertiary">
                    <Button variant="secondary" onClick={() => setShowConfig(true)}>
                        Add Connection
                    </Button>
                </Card.Footer>
            </Card>
            <ConnectionConfigModal show={showConfig} handleClose={() => setShowConfig(false)} />
        </>
    );
};

export default ConnectionStatus;
