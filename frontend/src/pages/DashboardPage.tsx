import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Card, ListGroup, Table } from 'react-bootstrap';
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
  Cell,
  ResponsiveContainer
} from 'recharts';
import { fetchAverageTemperature, fetchRunningSparkJobs, fetchTemperatureAlerts } from '../api/backendRequests';
import { FaChartLine, FaThermometerHalf, FaTasks, FaMapMarkerAlt, FaBell } from 'react-icons/fa'; // Import icons

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
  const [loading, setLoading] = useState<boolean>(true);
  const [runningJobs, setRunningJobs] = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs] = useState<boolean>(true);
  const [timeRange, setTimeRange] = useState<number>(24); // new state for time range
  const [temperatureAlerts, setTemperatureAlerts] = useState<any[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await fetchAverageTemperature();
        // Format the time_start field for proper display on the X-axis
        const formattedData = data.map((item: any) => ({
          ...item,
          time_start: new Date(item.time_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }));
        // Compare new data with the existing state to avoid unnecessary updates
        if (JSON.stringify(formattedData) !== JSON.stringify(averageTemperature)) {
          setAverageTemperature(formattedData);
        }
      } catch (error) {
        console.error("Error fetching average temperature:", error);
      } finally {
        if (loading) setLoading(false); // Only stop loading indicator after the first load
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 15000); // Refresh every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, [averageTemperature, loading]);

  useEffect(() => {
    const fetchJobs = async () => {
      setLoadingJobs(true);
      try {
        const data = await fetchRunningSparkJobs();
        setRunningJobs(data);
      } catch (error) {
        console.error("Error fetching running Spark jobs:", error);
      } finally {
        setLoadingJobs(false);
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 15000); // Fetch every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const data = await fetchTemperatureAlerts();
        setTemperatureAlerts(data);
      } catch (error) {
        console.error("Error fetching temperature alerts:", error);
      } finally {
        setLoadingAlerts(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 15000); // Poll every 15 seconds
    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

  return (
    <Container className="mt-3">
      <h1>Dashboard</h1>
      <Row className="mt-4">
        <Col md={6}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>
                <FaChartLine className="me-2" /> Monthly Sensors Trend
              </Card.Title>
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
              <Card.Title>
                <FaMapMarkerAlt className="me-2" /> Sensor Distribution
              </Card.Title>
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
              <Card.Title>
                <FaThermometerHalf className="me-2" /> Status Distribution
              </Card.Title>
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
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>
                <FaBell className="me-2" /> Event Feed
              </Card.Title>
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
              <Card.Title>
                <FaThermometerHalf className="me-2" /> Hourly Average Temperature
              </Card.Title>
              {/* Updated select for time range with more options */}
              <div className="mb-3">
                <label htmlFor="tempRangeSelect" className="form-label">Select Time Range:</label>
                <select
                  id="tempRangeSelect"
                  value={timeRange}
                  onChange={e => setTimeRange(Number(e.target.value))}
                  className="form-select"
                >
                  <option value={5}>Last 5 minutes</option>
                  <option value={15}>Last 15 minutes</option>
                  <option value={30}>Last 30 minutes</option>
                  <option value={60}>Last 1 hour</option>
                  <option value={120}>Last 2 hours</option>
                  <option value={0}>All</option>
                </select>
              </div>
              {loading ? (
                <div>Loading...</div>
              ) : (
                // Use ResponsiveContainer to fill the entire card
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart
                    data={timeRange === 0 ? averageTemperature : averageTemperature.slice(-timeRange)}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="time_start" // Updated to use time_start
                      label={{ value: 'Time', position: 'insideBottomRight', offset: -5 }}
                    />
                    <YAxis label={{ value: 'Avg Temp (°C)', angle: -90, position: 'insideLeft' }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="avg_temp" stroke="#8884d8" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mt-4">
        <Col md={12}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>
                <FaTasks className="me-2" /> Running Spark Jobs
              </Card.Title>
              {loadingJobs ? (
                <div>Loading...</div>
              ) : runningJobs.length > 0 ? (
                <Table striped bordered hover>
                  <thead>
                    <tr>
                      <th>App Name</th>
                      <th>Job ID</th>
                      <th>Status</th>
                      <th>Submission Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runningJobs.map((job, index) => (
                      <tr key={index}>
                        <td>{job.app_name}</td>
                        <td>{job.job_id}</td>
                        <td>{job.status}</td>
                        <td>{job.submission_time}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <div>No running jobs found.</div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mt-4">
        <Col md={12}>
          <Card className="mb-3">
            <Card.Body>
              <Card.Title>
                <FaBell className="me-2" /> Temperature Alerts
              </Card.Title>
              {loadingAlerts ? (
                <div>Loading...</div>
              ) : temperatureAlerts.length > 0 ? (
                <ListGroup variant="flush">
                  {temperatureAlerts.map((alert, index) => (
                    <ListGroup.Item key={index}>
                      <strong>Sensor:</strong> {alert.sensorId} | 
                      <strong> Temp:</strong> {alert.temperature}°C | 
                      <strong> Time:</strong> {alert.event_time}
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              ) : (
                <div>No alerts found.</div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default DashboardPage;
