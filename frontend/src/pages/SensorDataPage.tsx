import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Form, Button, Spinner } from 'react-bootstrap';
import ReactJson from 'react-json-view';

interface SensorData {
    temperature?: number;
    humidity?: number;
}

const SensorDataPage: React.FC = () => {
    const [data, setData] = useState<SensorData[]>([]);
    const [selectedPlace, setSelectedPlace] = useState<string>('');

    const fetchData = async () => {
        try {
            const response = await fetch('http://localhost:8000/data');
            const json = await response.json();
            setData(json);
        } catch (error) {
            console.error('Error fetching sensor data:', error);
        } finally {
        }
    };

    useEffect(() => {
        // Fetch data immediately and then every 5 seconds
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const handlePlaceChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedPlace(event.target.value);
    };

    const handleFormSubmit = (event: React.FormEvent) => {
        event.preventDefault();
        // Fetch data based on selected place
        fetchData();
    };

    return (
        <Container>
            <Row>
                <Col md={4}>
                    <h1>Select Place</h1>
                    <Form onSubmit={handleFormSubmit}>
                        <Form.Group controlId="placeSelect">
                            <Form.Label>Place</Form.Label>
                            <Form.Select value={selectedPlace} onChange={handlePlaceChange}>
                                <option value="">Select a place</option>
                                <option value="place1">Place 1</option>
                                <option value="place2">Place 2</option>
                                <option value="place3">Place 3</option>
                            </Form.Select>
                        </Form.Group>
                        <Button variant="primary" type="submit" className="mt-3">
                            Fetch Data
                        </Button>
                    </Form>
                </Col>
                <Col md={8}>
                    <h1>Sensor Data</h1>
                    {data && data.length > 0 ? (
                        <div style={{ padding: '10px', borderRadius: '5px', border: '1px solid #ccc', maxHeight: '70vh', overflowY: 'auto' }}>
                            <ReactJson src={data} theme="tomorrow" collapsed={false} />
                        </div>
                    ) : (
                        <Spinner animation="border" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </Spinner>
                    )}
                </Col>
            </Row>
        </Container>
    );
};

export default SensorDataPage;