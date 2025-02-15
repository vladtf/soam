import React, { useEffect, useState } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import SensorData from '../components/SensorData';

interface SensorData {
    temperature?: number;
    humidity?: number;
}

const SensorDataPage: React.FC = () => {
    const [data, setData] = useState<SensorData>({});

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
                <Col>
                    <h1>Sensor Data</h1>
                    <SensorData data={data} />
                </Col>
            </Row>
        </Container>
    );
};

export default SensorDataPage;
