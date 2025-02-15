import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';

const Home: React.FC = () => {
  return (
    <Container>
      <Row>
        <Col>
          <h1>Welcome to My Smart City Middleware</h1>
          <p>This is the home page.</p>
        </Col>
      </Row>
      <Row>
        <Col>
          <Card>
            <Card.Body>
              <Card.Title>Overview</Card.Title>
              <Card.Text>
                Our smart city middleware integrates various sensors and systems to provide real-time data and analytics for efficient city management.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row>
        <Col>
          <Card>
            <Card.Body>
              <Card.Title>Features</Card.Title>
              <div>
                <ul>
                  <li>Real-time sensor data monitoring</li>
                  <li>Data analytics and visualization</li>
                  <li>Automated alerts and notifications</li>
                  <li>Integration with existing city infrastructure</li>
                </ul>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row>
        <Col>
          <Card>
            <Card.Body>
              <Card.Title>Contact Us</Card.Title>
              <Card.Text>
                For more information, please contact us at <a href="mailto:info@smartcity.com">info@smartcity.com</a>.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default Home;
