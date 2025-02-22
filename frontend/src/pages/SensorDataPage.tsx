import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Spinner } from 'react-bootstrap';
import ReactJson from 'react-json-view';
import SensorForm from '../components/SensorForm';
import ConnectionStatus from '../components/ConnectionStatus';
import { fetchSensorData, extractDataSchema, SensorData } from '../api/backendQuery';

const SensorDataPage: React.FC = () => {
    const [data, setData] = useState<SensorData[]>([]);
    const [dataSchema, setDataSchema] = useState<Record<string, string[]>>({});

    useEffect(() => {
        const fetchData = async () => {
            try {
                const sensorData = await fetchSensorData();
                setData(sensorData);
                setDataSchema(extractDataSchema(sensorData));
            } catch (error) {
                console.error('Error fetching sensor data:', error);
            }
        };

        // Fetch data immediately and then every 5 seconds
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <Container className="mt-3">
            <ConnectionStatus />
            <Row>
                <Col md={6}>
                    <SensorForm dataSchema={dataSchema}  />
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