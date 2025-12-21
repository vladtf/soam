import React, { useContext } from 'react';
import { Container, Row, Col, Card, Badge } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { 
  FaChartLine, 
  FaSitemap, 
  FaTachometerAlt, 
  FaMapMarkedAlt, 
  FaChartBar, 
  FaDatabase, 
  FaCloud, 
  FaServer, 
  FaProjectDiagram, 
  FaDocker,
  FaCogs,
  FaNetworkWired,
  FaExternalLinkAlt,
  FaRocket,
  FaShieldAlt,
  FaBolt
} from 'react-icons/fa';
import { ConfigContext } from '../context/ConfigContext';
import { useTheme } from '../context/ThemeContext';
import { defaultExternalServices } from '../config';
import ErrorTestComponent from '../components/ErrorTestComponent';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  to?: string;
  href?: string;
  variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'dark' | 'info';
  badge?: string;
  portForwardCmd?: string;
  isDark?: boolean;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ 
  icon, 
  title, 
  description, 
  to, 
  href, 
  variant = 'primary',
  badge,
  portForwardCmd,
  isDark = false
}) => {
  const isExternalDisabled = !href && portForwardCmd;
  const headerBg = isExternalDisabled ? 'bg-secondary' : `bg-${variant}`;

  return (
    <Card className={`h-100 shadow-sm ${isExternalDisabled ? 'opacity-75' : ''}`} bg={isDark ? 'dark' : undefined} text={isDark ? 'light' : undefined}>
      <div className={`${headerBg} text-white p-3 d-flex align-items-center gap-2`}>
        <span className="fs-4">{icon}</span>
        <div>
          <h5 className="mb-0 d-flex align-items-center gap-2">
            {title}
            {badge && <Badge bg="light" text="dark" className="small">{badge}</Badge>}
            {isExternalDisabled && <Badge bg="dark" className="small">Port-Forward</Badge>}
          </h5>
        </div>
      </div>
      <Card.Body className="d-flex flex-column">
        <Card.Text className={`small flex-grow-1 ${isDark ? 'text-light opacity-75' : 'text-muted'}`}>
          {description}
        </Card.Text>
        {isExternalDisabled && portForwardCmd && (
          <code className={`d-block mb-2 p-2 rounded small text-break ${isDark ? 'bg-black text-warning' : 'bg-light'}`}>
            {portForwardCmd}
          </code>
        )}
        {to ? (
          <Link to={to} className={`btn btn-outline-${variant} btn-sm mt-2`}>
            Open <FaExternalLinkAlt size={10} className="ms-1" />
          </Link>
        ) : href ? (
          <a 
            href={href} 
            target="_blank" 
            rel="noopener noreferrer" 
            className={`btn btn-outline-${variant} btn-sm mt-2`}
          >
            Open <FaExternalLinkAlt size={10} className="ms-1" />
          </a>
        ) : null}
      </Card.Body>
    </Card>
  );
};

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => (
  <div className="text-center p-3">
    <div className="fs-2 text-primary">{icon}</div>
    <h3 className="mb-0 mt-2">{value}</h3>
    <small className="text-body-secondary">{label}</small>
  </div>
);

const Home: React.FC = () => {
  const config = useContext(ConfigContext);
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const services = config?.externalServices ?? defaultExternalServices;

  return (
    <div>
      {/* Hero Section */}
      <div className="bg-primary text-white text-center py-5">
        <Container>
          <h1 className="display-4 fw-bold mb-3">
            Smart City IoT Platform
          </h1>
          <p className="lead mb-4 mx-auto col-lg-8">
            Unified middleware for real-time sensor data aggregation, processing, and visualization
          </p>
          <div className="d-flex gap-3 flex-wrap justify-content-center">
            <Link to="/dashboard" className="btn btn-light btn-lg px-4">
              <FaTachometerAlt className="me-2" /> Dashboard
            </Link>
            <Link to="/pipeline" className="btn btn-outline-light btn-lg px-4">
              <FaCogs className="me-2" /> Data Pipeline
            </Link>
          </div>
        </Container>
      </div>

      {/* Stats Section */}
      <Container className="py-4">
        <Card className="shadow-sm mb-4" bg={isDark ? 'dark' : undefined} text={isDark ? 'light' : undefined}>
          <Card.Body>
            <Row>
              <Col xs={6} md={3}>
                <StatCard icon={<FaNetworkWired />} label="Data Sources" value="Multi" />
              </Col>
              <Col xs={6} md={3}>
                <StatCard icon={<FaBolt />} label="Processing" value="Real-time" />
              </Col>
              <Col xs={6} md={3}>
                <StatCard icon={<FaRocket />} label="Spark Streaming" value="Active" />
              </Col>
              <Col xs={6} md={3}>
                <StatCard icon={<FaShieldAlt />} label="Security" value="JWT Auth" />
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Platform Features */}
        <h4 className="mb-3 text-body-secondary">
          <FaCogs className="me-2" /> Platform Features
        </h4>
        <Row className="g-3 mb-4">
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaTachometerAlt />}
              title="Dashboard"
              description="Create custom tiles with real-time data visualization, time series charts, and auto-refresh."
              to="/dashboard"
              variant="primary"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaCogs />}
              title="Data Pipeline"
              description="Configure normalization rules, value transformations, and manage data flow."
              to="/pipeline"
              variant="success"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaChartLine />}
              title="Data Sources"
              description="Register and manage MQTT, REST API, and other data connectors."
              to="/data-sources"
              variant="info"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaSitemap />}
              title="Ontology"
              description="Explore the knowledge graph structure and semantic relationships."
              to="/ontology"
              variant="secondary"
              isDark={isDark}
            />
          </Col>
        </Row>

        <Row className="g-3 mb-4">
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaDatabase />}
              title="MinIO Browser"
              description="Browse raw and processed data stored in the object storage lake."
              to="/minio"
              variant="danger"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaMapMarkedAlt />}
              title="Interactive Map"
              description="Visualize sensor locations and city infrastructure geospatially."
              to="/map"
              variant="primary"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaProjectDiagram />}
              title="Schema Metadata"
              description="View inferred schemas, field statistics, and data evolution."
              to="/metadata"
              variant="success"
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={3}>
            <FeatureCard
              icon={<FaCogs />}
              title="Settings"
              description="Configure application preferences and system parameters."
              to="/settings"
              variant="info"
              isDark={isDark}
            />
          </Col>
        </Row>

        {/* External Services */}
        <h4 className="mb-3 text-body-secondary">
          <FaServer className="me-2" /> Infrastructure Services
        </h4>
        <Row className="g-3 mb-4">
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaChartBar />}
              title="Grafana"
              description="Advanced monitoring dashboards with custom visualizations and alerting."
              href={services.grafanaUrl || undefined}
              variant="danger"
              badge="External"
              portForwardCmd={!services.grafanaUrl ? "kubectl port-forward svc/grafana 3001:3000 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaDatabase />}
              title="Prometheus"
              description="Metrics collection, time-series database, and alerting rules."
              href={services.prometheusUrl || undefined}
              variant="info"
              badge="External"
              portForwardCmd={!services.prometheusUrl ? "kubectl port-forward svc/prometheus 9091:9090 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaServer />}
              title="Spark Master"
              description="Apache Spark cluster management and streaming job monitoring."
              href={services.sparkMasterUrl || undefined}
              variant="success"
              badge="External"
              portForwardCmd={!services.sparkMasterUrl ? "kubectl port-forward svc/soam-spark-master-svc 8080:80 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
        </Row>

        <Row className="g-3 mb-4">
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaCloud />}
              title="MinIO Console"
              description="Object storage administration, bucket management, and access policies."
              href={services.minioUrl || undefined}
              variant="primary"
              badge="External"
              portForwardCmd={!services.minioUrl ? "kubectl port-forward svc/minio 9090:9090 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaProjectDiagram />}
              title="Neo4j Browser"
              description="Graph database interface for exploring ontology and relationships."
              href={services.neo4jUrl || undefined}
              variant="secondary"
              badge="External"
              portForwardCmd={!services.neo4jUrl ? "kubectl port-forward svc/neo4j 7474:7474 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
          <Col md={6} lg={4}>
            <FeatureCard
              icon={<FaDocker />}
              title="cAdvisor"
              description="Container resource usage monitoring and performance analysis."
              href={services.cadvisorUrl || undefined}
              variant="danger"
              badge="External"
              portForwardCmd={!services.cadvisorUrl ? "kubectl port-forward svc/cadvisor 8089:8080 -n soam" : undefined}
              isDark={isDark}
            />
          </Col>
        </Row>

        {/* About Section */}
        <Card className="shadow-sm mb-4" bg={isDark ? 'dark' : 'light'} text={isDark ? 'light' : undefined}>
          <Card.Body className="p-4">
            <Row className="align-items-center">
              <Col md={8}>
                <h4 className="mb-3">About SOAM Platform</h4>
                <p className={`mb-0 ${isDark ? 'text-light opacity-75' : 'text-muted'}`}>
                  SOAM (Smart City Open Aggregation Middleware) integrates diverse IoT sensors and data sources 
                  into a unified platform. Built with Python/FastAPI backend, React/TypeScript frontend, 
                  Apache Spark for stream processing, and Kubernetes for orchestration. Features include 
                  real-time data ingestion, schema inference, configurable normalization, and AI-powered 
                  computation generation.
                </p>
              </Col>
              <Col md={4} className="text-center">
                <div className="d-flex flex-column gap-2 align-items-center">
                  <Badge bg="primary" className="px-3 py-2">Python • FastAPI</Badge>
                  <Badge bg="dark" className="px-3 py-2">React • TypeScript</Badge>
                  <Badge bg="success" className="px-3 py-2">Spark • Kubernetes</Badge>
                </div>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        {/* Error Testing Component - Development Only */}
        <ErrorTestComponent />
      </Container>
    </div>
  );
};

export default Home;
