import React, { useState } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

interface ConnectionConfigModalProps {
    show: boolean;
    handleClose: () => void;
}

const ConnectionConfigModal: React.FC<ConnectionConfigModalProps> = ({ show, handleClose }) => {
    const [connectionType, setConnectionType] = useState('mqtt');
    const [brokerOption, setBrokerOption] = useState('localhost');
    const [customBroker, setCustomBroker] = useState('');
    const [port, setPort] = useState(1883);
    const [topic, setTopic] = useState('smartcity/sensor');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const broker = (connectionType === 'mqtt' && brokerOption !== 'custom') ? brokerOption : customBroker;
        const config = { connectionType, broker, port, topic };
        await fetch('http://localhost:8000/addConnection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        handleClose();
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>Configure Sensor Connection</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form onSubmit={handleSubmit}>
                    <Form.Group controlId="formConnectionType">
                        <Form.Label>Connection Type</Form.Label>
                        <Form.Control 
                            as="select" 
                            value={connectionType}
                            onChange={e => setConnectionType(e.target.value)}
                        >
                            <option value="mqtt">MQTT</option>
                            <option value="other">Other (Coming Soon)</option>
                        </Form.Control>
                    </Form.Group>
                    {connectionType === 'mqtt' ? (
                        <>
                            <Form.Group controlId="formBrokerSelect" className="mt-2">
                                <Form.Label>MQTT Broker</Form.Label>
                                <Form.Control 
                                    as="select" 
                                    value={brokerOption}
                                    onChange={e => setBrokerOption(e.target.value)}
                                >
                                    <option value="localhost">localhost</option>
                                    <option value="broker.hivemq.com">broker.hivemq.com</option>
                                    <option value="test.mosquitto.org">test.mosquitto.org</option>
                                    <option value="custom">Custom</option>
                                </Form.Control>
                            </Form.Group>
                            {brokerOption === 'custom' && (
                                <Form.Group controlId="formCustomBroker" className="mt-2">
                                    <Form.Label>Custom Broker</Form.Label>
                                    <Form.Control
                                        type="text"
                                        placeholder="Enter custom broker"
                                        value={customBroker}
                                        onChange={e => setCustomBroker(e.target.value)}
                                    />
                                </Form.Group>
                            )}
                            <Form.Group controlId="formPort" className="mt-2">
                                <Form.Label>Port</Form.Label>
                                <Form.Control
                                    type="number"
                                    placeholder="Enter port"
                                    value={port}
                                    onChange={e => setPort(+e.target.value)}
                                />
                            </Form.Group>
                            <Form.Group controlId="formTopic" className="mt-2">
                                <Form.Label>Topic</Form.Label>
                                <Form.Control
                                    type="text"
                                    placeholder="Enter topic"
                                    value={topic}
                                    onChange={e => setTopic(e.target.value)}
                                />
                            </Form.Group>
                        </>
                    ) : (
                        <p className="mt-2">Configuration for connection type "Other" is not implemented yet.</p>
                    )}
                    <Button variant="primary" type="submit" className="mt-3">
                        Save Configuration
                    </Button>
                </Form>
            </Modal.Body>
        </Modal>
    );
};

export default ConnectionConfigModal;
