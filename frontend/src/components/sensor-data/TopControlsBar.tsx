import React from 'react';
import { Row, Col, Form, Button, Card, InputGroup } from 'react-bootstrap';

export interface TopControlsBarProps {
    partitions: string[];
    activePartition: string;
    setActivePartition: (v: string) => void;
    bufferSize: number;
    setBufferSize: (n: number) => void;
    applyBufferSize: (e: React.FormEvent) => void;
    viewMode: 'table' | 'json';
    setViewMode: (v: 'table' | 'json') => void;
}

const TopControlsBar: React.FC<TopControlsBarProps> = ({
    partitions,
    activePartition,
    setActivePartition,
    bufferSize,
    setBufferSize,
    applyBufferSize,
    viewMode,
    setViewMode,
}) => {
    return (
        <Card className="mb-3">
            <Card.Body className="py-2">
                <Row className="g-2 align-items-center">
                    <Col lg={4} md={6}>
                        <Form.Group controlId="partitionSelect" className="mb-0">
                            <InputGroup size="sm">
                                <InputGroup.Text>Partition</InputGroup.Text>
                                <Form.Select value={activePartition} onChange={(e) => setActivePartition(e.target.value)}>
                                    <option value="">All</option>
                                    {partitions.map((p) => (
                                        <option key={p} value={p}>{p}</option>
                                    ))}
                                </Form.Select>
                                <InputGroup.Text className="text-muted">{partitions.length}</InputGroup.Text>
                            </InputGroup>
                        </Form.Group>
                    </Col>
                    <Col lg={4} md={6}>
                        <Form onSubmit={applyBufferSize} className="mb-0">
                            <InputGroup size="sm">
                                <InputGroup.Text>Max rows</InputGroup.Text>
                                <Form.Control type="number" min={1} value={bufferSize} onChange={(e) => setBufferSize(parseInt(e.target.value || '1', 10))} />
                                <Button type="submit" variant="outline-secondary">Apply</Button>
                            </InputGroup>
                        </Form>
                    </Col>
                    <Col lg={4} md={12}>
                        <Form.Group className="mb-0">
                            <InputGroup size="sm">
                                <InputGroup.Text>View</InputGroup.Text>
                                <Form.Select value={viewMode} onChange={(e) => setViewMode(e.target.value as 'table' | 'json')}>
                                    <option value="json">JSON</option>
                                    <option value="table">Table</option>
                                </Form.Select>
                            </InputGroup>
                        </Form.Group>
                    </Col>
                </Row>
            </Card.Body>
        </Card>
    );
};

export default TopControlsBar;
