import React from 'react';
import { Row, Col, Card, ListGroup } from 'react-bootstrap';
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
import { FaChartLine, FaThermometerHalf, FaMapMarkerAlt, FaBell } from 'react-icons/fa';

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

const StatisticsCards: React.FC = () => {
  return (
    <>
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
    </>
  );
};

export default StatisticsCards;
