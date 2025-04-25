import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Card, ListGroup } from 'react-bootstrap';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';

const lineData = [
  { name: 'Jan', sensors: 20 },
  { name: 'Feb', sensors: 35 },
  { name: 'Mar', sensors: 25 },
  { name: 'Apr', sensors: 40 },
  { name: 'May', sensors: 30 }
];

const barData = [
  { name: 'Sensor A', value: 400 },
  { name: 'Sensor B', value: 300 },
  { name: 'Sensor C', value: 200 },
  { name: 'Sensor D', value: 278 },
  { name: 'Sensor E', value: 189 }
];

const pieData = [
  { name: 'Active', value: 400 },
  { name: 'Inactive', value: 300 }
];

const COLORS = ['#0088FE', '#FF8042'];

// Mocked events for the event feed board.
const events = [
  { id: 1, time: '10:00 AM', description: 'Sensor A reported high temperature.' },
  { id: 2, time: '10:05 AM', description: 'Sensor B went offline.' },
  { id: 3, time: '10:10 AM', description: 'Sensor C recovered from error.' },
  { id: 4, time: '10:15 AM', description: 'Sensor D reported normal values.' }
];

const DashboardPage: React.FC = () => {
  const [averageTemperature, setAverageTemperature] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true); // Add loading state
  const [runningJobs, setRunningJobs] = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs] = useState<boolean>(true);

  useEffect(() => {
    // Fetch average temperature data from the backend
    const fetchAverageTemperature = async () => {
      setLoading(true); // Set loading to true before the API call
      try {
        const response = await fetch("http://localhost:8000/averageTemperature");
        const data = await response.json();
        if (data.status === "success") {
          setAverageTemperature(data.data);
        } else {
          console.error("Error fetching average temperature:", data.detail);
        }
      } catch (error) {
        console.error("Error fetching average temperature:", error);
      } finally {
        setLoading(false); // Set loading to false after the API call
      }
    };

    fetchAverageTemperature();
  }, []);

  useEffect(() => {
    // Fetch running Spark jobs from the backend every 15 seconds
    const fetchRunningJobs = async () => {
      setLoadingJobs(true);
      try {
        const response = await fetch("http://localhost:8000/runningSparkJobs");
        const data = await response.json();
        if (data.status === "success") {
          setRunningJobs(data.data);
        } else {
          console.error("Error fetching running Spark jobs:", data.detail);
        }
      } catch (error) {
        console.error("Error fetching running Spark jobs:", error);
      } finally {
        setLoadingJobs(false);
      }
    };

    fetchRunningJobs();
    const interval = setInterval(fetchRunningJobs, 5000); // Fetch every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

  return (
    <Container className="mt-3">
      <h1>Dashboard</h1>
      <Row className="mt-4">
        <Col md={6}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Monthly Sensors Trend</Card.Title>
              <LineChart width={400} height={300} data={lineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="sensors" stroke="#8884d8" activeDot={{ r: 8 }} />
              </LineChart>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Sensor Distribution</Card.Title>
              <BarChart width={400} height={300} data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="value" fill="#82ca9d" />
              </BarChart>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mt-4">
        <Col md={6}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Status Distribution</Card.Title>
              <PieChart width={400} height={300}>
                <Pie 
                  data={pieData} 
                  cx={200} 
                  cy={150} 
                  outerRadius={80} 
                  fill="#8884d8" 
                  dataKey="value"
                  label
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6}>
          {/* New Event Feed Board */}
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Event Feed</Card.Title>
              <ListGroup variant="flush">
                {events.map(event => (
                  <ListGroup.Item key={event.id}>
                    <strong>{event.time}</strong>: {event.description}
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mt-4">
        <Col md={12}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Hourly Average Temperature</Card.Title>
              {loading ? ( // Show loading effect while data is being fetched
                <div>Loading...</div>
              ) : (
                <ListGroup variant="flush">
                  {averageTemperature.map((entry, index) => (
                    <ListGroup.Item key={index}>
                      <strong>Date:</strong> {entry.date}, <strong>Hour:</strong> {entry.hour}, <strong>Avg Temp:</strong> {entry.avg_temp.toFixed(2)} °C
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mt-4">
        <Col md={12}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>Running Spark Jobs</Card.Title>
              {loadingJobs ? (
                <div>Loading...</div>
              ) : runningJobs.length > 0 ? (
                <ListGroup variant="flush">
                  {runningJobs.map((job, index) => (
                    <ListGroup.Item key={index}>
                      <strong>App Name:</strong> {job.app_name}, <strong>Job ID:</strong> {job.job_id}, <strong>Status:</strong> {job.status}, <strong>Submission Time:</strong> {job.submission_time}
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              ) : (
                <div>No running jobs found.</div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default DashboardPage;
