import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';

const Home: React.FC = () => {
  return (
    <Container fluid className="p-0">
      {/* Hero Section */}
      <div
        style={{
          background: "url('https://source.unsplash.com/1600x400/?city') no-repeat center center",
          backgroundSize: "cover",
          height: "400px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          textShadow: "2px 2px 4px rgba(0,0,0,0.7)"
        }}
      >
        <h1>Welcome to Smart City Middleware</h1>
      </div>

      <Container className="mt-4">
        {/* Overview Cards */}
        <Row>
          <Col md={4}>
            <Card className="mb-4">
              <Card.Body>
                <Card.Title>Real-Time Sensor Data</Card.Title>
                <Card.Text>
                  Monitor sensor readings in real-time for effective city management.
                </Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-4">
              <Card.Body>
                <Card.Title>Comprehensive Analytics</Card.Title>
                <Card.Text>
                  Gain insights from detailed dashboards and graphical reports.
                </Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-4">
              <Card.Body>
                <Card.Title>Interactive Maps</Card.Title>
                <Card.Text>
                  Visualize sensor locations and city infrastructure on dynamic maps.
                </Card.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        {/* Information Section */}
        <Row className="mb-4">
          <Col>
            <Card>
              <Card.Body>
                <Card.Title>About Our Platform</Card.Title>
                <Card.Text>
                  Our middleware integrates diverse city sensors and data sources, providing real-time analytics and decision support to enhance urban living. Explore our dashboards, maps, and ontologies to learn how we streamline city operations.
                </Card.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Container>
    </Container>
  );
};

export default Home;
