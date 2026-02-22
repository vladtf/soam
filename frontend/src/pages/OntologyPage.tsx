import React, { useState } from 'react';
import { Container, Row, Col, Tabs, Tab } from 'react-bootstrap';
import OntologyViewer from '../components/OntologyViewer';
import KnowledgeGraphViewer from '../components/KnowledgeGraphViewer';

const OntologyPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('knowledge-graph');

  return (
    <Container className="pt-3 pb-4">
      <Row className="g-3">
        <Col>
          <h1>🌐 Ontology & Knowledge Graph</h1>
          <p className="text-muted mb-3">
            Explore the ontology schema definition and the live knowledge graph of your smart city entities.
          </p>
          <Tabs activeKey={activeTab} onSelect={(k) => setActiveTab(k || 'knowledge-graph')} className="mb-3">
            <Tab eventKey="knowledge-graph" title="📊 Knowledge Graph (Live Data)">
              <KnowledgeGraphViewer />
            </Tab>
            <Tab eventKey="schema" title="📐 Ontology Schema (OWL)">
              <OntologyViewer />
            </Tab>
          </Tabs>
        </Col>
      </Row>
    </Container>
  );
};

export default OntologyPage;
