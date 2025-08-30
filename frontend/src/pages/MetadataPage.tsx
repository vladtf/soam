import React from 'react';
import { Container } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import MetadataViewer from '../components/MetadataViewer';

const MetadataPage: React.FC = () => {
  return (
    <Container className="py-3">
      <PageHeader 
        title="Metadata" 
        subtitle="View ingestion metadata, schemas, and statistics"
      />
      <MetadataViewer className="mt-3" />
    </Container>
  );
};

export default MetadataPage;
