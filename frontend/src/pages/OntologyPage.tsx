import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import OntologyViewer from '../components/OntologyViewer';

const OntologyPage: React.FC = () => {
  return (
    <Container>
      <Row>
        <Col>
          <h1>Ontology Viewer</h1>
          <OntologyViewer />
        </Col>
      </Row>
    </Container>
  );
};

export default OntologyPage;
