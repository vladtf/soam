import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Spinner, Form, Button } from 'react-bootstrap';
import ReactJson from 'react-json-view';
import DynamicForm from '../components/DynamicForm';
import SensorForm from '../components/SensorForm';

interface SensorData {
    temperature?: number;
    humidity?: number;
}


interface SensorFormData {
    [propertyURI: string]: string;
}

const SensorDataPage: React.FC = () => {
    const [data, setData] = useState<SensorData[]>([]);
    const [formData, setFormData] = useState<SensorFormData>({});


    const fetchData = async () => {
        try {
            const response = await fetch('http://localhost:8000/data');
            const json = await response.json();
            setData(json);
        } catch (error) {
            console.error('Error fetching sensor data:', error);
        }
    };

    useEffect(() => {
        // Fetch data immediately and then every 5 seconds
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        // You can add further validation if needed.
        console.log("Submitted Sensor Data:", formData);
        // Process formData as needed (e.g. create RDF triples for the sensor instance)
    };

    return (
        <Container>
            <Row>
                <Col md={6}>
                    <SensorForm />
                </Col>
                <Col md={6}>
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