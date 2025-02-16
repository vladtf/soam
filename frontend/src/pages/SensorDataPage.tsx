import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Spinner } from 'react-bootstrap';
import ReactJson from 'react-json-view';
import DynamicSensorForm from '../components/DynamicSensorForm';

interface SensorData {
    temperature?: number;
    humidity?: number;
}

const SensorDataPage: React.FC = () => {
    const [data, setData] = useState<SensorData[]>([]);

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

    return (
        <Container>
            <Row>
                <Col md={4}>
                    <DynamicSensorForm />
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