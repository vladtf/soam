import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import OntologyViewer from '../components/OntologyViewer';

const OntologyPage: React.FC = () => {
  return (
    <Container className="pt-3 pb-4">
      <Row className="g-3">
        <Col>
          <h1>Ontology Viewer</h1>
          <OntologyViewer />
        </Col>
      </Row>
    </Container>
  );
};

export default OntologyPage;
