import React, { useEffect, useState } from 'react';
import { Card, Dropdown } from 'react-bootstrap';

interface Connection {
    id: number;
    broker: string;
    port: number;
    topic: string;
    connectionType?: string;
}

const MQTTBrokerSwitcher: React.FC = () => {
    const [connections, setConnections] = useState<Connection[]>([]);
    const [active, setActive] = useState<Connection | null>(null);

    useEffect(() => {
        const fetchConnections = async () => {
            try {
                const response = await fetch('http://localhost:8000/connections');
                const data = await response.json();
                setConnections(data.connections);
                setActive(data.active);
            } catch (error) {
                console.error('Error fetching connections:', error);
            }
        };
        fetchConnections();
        const interval = setInterval(fetchConnections, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleSwitch = async (id: number) => {
        await fetch('http://localhost:8000/switchBroker', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
    };

    return (
        <Card className="mb-3">
            <Card.Header>MQTT Broker Switcher</Card.Header>
            <Card.Body>
                {connections.length > 0 ? (
                    <Dropdown>
                        <Dropdown.Toggle variant="secondary" id="dropdown-basic">
                            {active ? `Active: ${active.broker}` : "Select Active Broker"}
                        </Dropdown.Toggle>
                        <Dropdown.Menu>
                            {connections.map(conn => (
                                <Dropdown.Item key={conn.id} onClick={() => handleSwitch(conn.id)}>
                                    {conn.broker} (Port: {conn.port})
                                </Dropdown.Item>
                            ))}
                        </Dropdown.Menu>
                    </Dropdown>
                ) : (
                    "No connections configured."
                )}
            </Card.Body>
        </Card>
    );
};

export default MQTTBrokerSwitcher;
