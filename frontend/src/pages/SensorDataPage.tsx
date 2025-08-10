import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Spinner } from 'react-bootstrap';
import ReactJson from 'react-json-view';
import SensorForm from '../components/SensorForm';
import ConnectionStatus from '../components/ConnectionStatus';
import { fetchSensorData, extractDataSchema, SensorData } from '../api/backendRequests';
import { useError } from '../context/ErrorContext';

const SensorDataPage: React.FC = () => {
    const { setError } = useError();
    const [data, setData] = useState<SensorData[]>([]);
    const [dataSchema, setDataSchema] = useState<Record<string, string[]>>({});

    useEffect(() => {
        const fetchData = async () => {
            try {
                const sensorData = await fetchSensorData();
                setData(sensorData);
                setDataSchema(extractDataSchema(sensorData));
            } catch (err: unknown) {
                console.error('Error fetching sensor data:', err);
                setError(err instanceof Error ? err.message : err);
            }
        };

        // Fetch data immediately and then every 5 seconds
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, [setError]);

    return (
        <Container className="pt-3 pb-4">
            <ConnectionStatus />
            <Row className="g-3">
                <Col md={6}>
                    <SensorForm dataSchema={dataSchema} />
                </Col>
                <Col md={6}>
                    <h1 className="h3 mb-3">Sensor Data</h1>
                    {data && data.length > 0 ? (
                        <div className="p-2 border rounded bg-body-tertiary" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
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