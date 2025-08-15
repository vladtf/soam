import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { FaChartLine, FaSitemap, FaTachometerAlt, FaMapMarkedAlt, FaChartBar, FaDatabase, FaCloud, FaServer, FaProjectDiagram, FaDocker } from 'react-icons/fa';

const Home: React.FC = () => {
  return (
    <Container fluid className="p-0">
      {/* Hero Section */}
      <div
        style={{
          background: "url('/assets/city-skyline.png') no-repeat center center",
          backgroundSize: "cover",
          height: "min(60vh, 400px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          textShadow: "clamp(1px, 0.5vw, 3px) clamp(1px, 0.5vw, 3px) clamp(2px, 1vw, 5px) rgba(0,0,0,0.7)"
        }}
      >
        <h1>Welcome to Smart City Middleware</h1>
      </div>

      <Container className="pt-3 pb-4">
        {/* Overview Cards */}
        <Row className="g-3">
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaChartLine /> Real-Time Sensor Data</Card.Title>
                <Card.Text>
                  Monitor sensor readings in real-time for effective city management.
                </Card.Text>
                <Link to="/sensor-data" className="btn btn-primary">Go to Sensor Data</Link>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaSitemap /> Ontology Viewer</Card.Title>
                <Card.Text>
                  Explore the ontology structure and relationships in the system.
                </Card.Text>
                <Link to="/ontology" className="btn btn-primary">Go to Ontology</Link>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaTachometerAlt /> Dashboard</Card.Title>
                <Card.Text>
                  View analytics and insights from the collected data.
                </Card.Text>
                <Link to="/dashboard" className="btn btn-primary">Go to Dashboard</Link>
              </Card.Body>
            </Card>
          </Col>
    </Row>
    <Row className="g-3">
          <Col md={4}>
      <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaMapMarkedAlt /> Interactive Map</Card.Title>
                <Card.Text>
                  Visualize sensor locations and city infrastructure on dynamic maps.
                </Card.Text>
                <Link to="/map" className="btn btn-primary">Go to Map</Link>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaChartBar /> Grafana</Card.Title>
                <Card.Text>
                  Access Grafana for monitoring and visualization of metrics.
                </Card.Text>
                <a href="http://localhost:3001" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to Grafana</a>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaDatabase /> Prometheus</Card.Title>
                <Card.Text>
                  Access Prometheus for metrics collection and alerting.
                </Card.Text>
                <a href="http://localhost:9091" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to Prometheus</a>
              </Card.Body>
            </Card>
          </Col>
    </Row>
    <Row className="g-3">
          <Col md={4}>
      <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaCloud /> MinIO</Card.Title>
                <Card.Text>
                  Access MinIO for object storage management.
                </Card.Text>
                <a href="http://localhost:9000" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to MinIO</a>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaServer /> Spark Master</Card.Title>
                <Card.Text>
                  Access the Spark Master Web UI for cluster management.
                </Card.Text>
                <a href="http://localhost:8080" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to Spark Master</a>
              </Card.Body>
            </Card>
          </Col>
        </Row>
        <Row className="g-3">
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaProjectDiagram /> Neo4j</Card.Title>
                <Card.Text>
                  Access the Neo4j Web UI for graph database management.
                </Card.Text>
                <a href="http://localhost:7474" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to Neo4j</a>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="mb-3 shadow-sm border-body">
              <Card.Body>
                <Card.Title><FaDocker /> cAdvisor</Card.Title>
                <Card.Text>
                  Access cAdvisor for container resource monitoring.
                </Card.Text>
                <a href="http://localhost:8089" target="_blank" rel="noopener noreferrer" className="btn btn-primary">Go to cAdvisor</a>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        {/* Information Section */}
        <Row className="mb-4">
          <Col>
            <Card className="shadow-sm border-body">
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
